import concurrent.futures
import ipaddress
import platform
import re
import socket
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "netwatch.db"
OUI_PATH = BASE_DIR / "oui.txt"

PING_TIMEOUT_MS = 300
MAX_WORKERS = 40

_OUI_CACHE = None


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Enable SQLite foreign-key enforcement.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT UNIQUE NOT NULL,
                ip_address TEXT,
                hostname TEXT,
                device_name TEXT,
                vendor TEXT,
                status TEXT NOT NULL DEFAULT 'Unknown',
                notes TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                times_seen INTEGER NOT NULL DEFAULT 1,
                online INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        # Upgrade an existing database without deleting it.
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(devices)"
            ).fetchall()
        }

        if "vendor" not in columns:
            conn.execute(
                """
                ALTER TABLE devices
                ADD COLUMN vendor TEXT
                """
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_devices_ip
            ON devices(ip_address)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_devices_status
            ON devices(status)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_devices_vendor
            ON devices(vendor)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                network TEXT,
                local_ip TEXT,
                active_ips_found INTEGER NOT NULL DEFAULT 0,
                devices_identified INTEGER NOT NULL DEFAULT 0,
                new_devices_found INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running'
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scans_started
            ON scans(started_at)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                mac_address TEXT NOT NULL,
                ip_address TEXT,
                hostname TEXT,
                observed_at TEXT NOT NULL,
                online INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (scan_id)
                    REFERENCES scans(id),
                FOREIGN KEY (mac_address)
                    REFERENCES devices(mac_address)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scan_history_scan
            ON scan_history(scan_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scan_history_mac
            ON scan_history(mac_address)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scan_history_time
            ON scan_history(observed_at)
            """
        )


# ---------------------------------------------------------
# Network detection
# ---------------------------------------------------------

def get_local_ip():
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    try:
        # No data is sent. This determines the preferred
        # local interface and its IP address.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


def get_network(local_ip):
    """
    This version assumes a typical /24 home network.

    Example:
        192.168.1.24 -> 192.168.1.0/24
    """
    return ipaddress.ip_network(
        f"{local_ip}/24",
        strict=False
    )


# ---------------------------------------------------------
# Ping sweep
# ---------------------------------------------------------

def ping_host(ip):
    ip = str(ip)
    system = platform.system()

    if system == "Windows":
        command = [
            "ping",
            "-n", "1",
            "-w", str(PING_TIMEOUT_MS),
            ip
        ]

        creationflags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0
        )

    elif system == "Darwin":
        command = [
            "ping",
            "-c", "1",
            "-W", "1000",
            ip
        ]

        creationflags = 0

    else:
        command = [
            "ping",
            "-c", "1",
            "-W", "1",
            ip
        ]

        creationflags = 0

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            timeout=3,
            check=False
        )

        if result.returncode == 0:
            return ip

    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError
    ):
        pass

    return None

def scan_network(network):
    hosts = list(network.hosts())

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        results = executor.map(
            ping_host,
            hosts
        )

    return [
        ip
        for ip in results
        if ip
    ]


# ---------------------------------------------------------
# MAC address helpers
# ---------------------------------------------------------

def normalize_mac(mac):
    if not mac:
        return ""

    cleaned = (
        mac.strip()
        .replace("-", ":")
        .replace(".", "")
        .upper()
    )

    # Handle Cisco-style aabb.ccdd.eeff addresses.
    if ":" not in cleaned and len(cleaned) == 12:
        parts = [
            cleaned[index:index + 2]
            for index in range(0, 12, 2)
        ]
    else:
        parts = cleaned.split(":")

    if len(parts) != 6:
        return cleaned.replace(":", "-")

    try:
        normalized_parts = [
            f"{int(part, 16):02X}"
            for part in parts
        ]
    except ValueError:
        return cleaned.replace(":", "-")

    return "-".join(normalized_parts)


def get_clean_mac(mac):
    return re.sub(
        r"[^0-9A-Fa-f]",
        "",
        mac or ""
    ).upper()


def is_locally_administered_mac(mac):
    clean_mac = get_clean_mac(mac)

    if len(clean_mac) != 12:
        return False

    try:
        first_octet = int(clean_mac[:2], 16)
    except ValueError:
        return False

    # The second-least-significant bit is the U/L bit.
    return bool(first_octet & 0x02)


def is_multicast_mac(mac):
    clean_mac = get_clean_mac(mac)

    if len(clean_mac) != 12:
        return False

    try:
        first_octet = int(clean_mac[:2], 16)
    except ValueError:
        return False

    # The least-significant bit is the I/G bit.
    return bool(first_octet & 0x01)


# ---------------------------------------------------------
# ARP
# ---------------------------------------------------------

def get_arp_table():
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=10,
            check=False
        )
    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError
    ):
        return {}

    arp_entries = {}
    system = platform.system()

    if system == "Windows":
        # Windows example:
        # 192.168.68.1    aa-bb-cc-dd-ee-ff    dynamic
        pattern = re.compile(
            r"(\d{1,3}(?:\.\d{1,3}){3})\s+"
            r"([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})"
        )

    else:
        # macOS/BSD example:
        # router.lan (192.168.68.1) at
        # a8:42:a1:3:4e:d3 on en0 ifscope [ethernet]
        #
        # Some macOS ARP octets are displayed with one
        # hexadecimal digit, so each octet accepts 1-2 digits.
        pattern = re.compile(
            r"\((\d{1,3}(?:\.\d{1,3}){3})\)"
            r"\s+at\s+"
            r"([0-9a-fA-F]{1,2}"
            r"(?::[0-9a-fA-F]{1,2}){5})"
        )

    for ip, mac in pattern.findall(result.stdout):
        normalized_mac = normalize_mac(mac)

        if normalized_mac:
            arp_entries[ip] = normalized_mac

    return arp_entries


# ---------------------------------------------------------
# IEEE OUI vendor lookup
# ---------------------------------------------------------

def load_oui_database():
    global _OUI_CACHE

    if _OUI_CACHE is not None:
        return _OUI_CACHE

    vendors = {}

    if not OUI_PATH.exists():
        _OUI_CACHE = vendors
        return vendors

    # IEEE oui.txt example:
    # 28-6F-B9   (hex)        Nokia Shanghai Bell Co., Ltd.
    hex_pattern = re.compile(
        r"^\s*"
        r"([0-9A-Fa-f]{2})-"
        r"([0-9A-Fa-f]{2})-"
        r"([0-9A-Fa-f]{2})"
        r"\s+\(hex\)\s+"
        r"(.+?)\s*$"
    )

    # Support simplified files such as:
    # 286FB9 Nokia Shanghai Bell Co., Ltd.
    compact_pattern = re.compile(
        r"^\s*"
        r"([0-9A-Fa-f]{6})"
        r"\s+"
        r"(.+?)\s*$"
    )

    with OUI_PATH.open(
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as oui_file:
        for line in oui_file:
            match = hex_pattern.match(line)

            if match:
                prefix = (
                    match.group(1)
                    + match.group(2)
                    + match.group(3)
                ).upper()

                vendor = match.group(4).strip()

                if vendor:
                    vendors[prefix] = vendor

                continue

            match = compact_pattern.match(line)

            if match:
                prefix = match.group(1).upper()
                vendor = match.group(2).strip()

                # Avoid treating IEEE address lines as vendors.
                if vendor and not vendor.startswith("("):
                    vendors.setdefault(prefix, vendor)

    _OUI_CACHE = vendors
    return vendors


def get_mac_vendor(mac):
    if not mac:
        return "Unknown"

    clean_mac = get_clean_mac(mac)

    if len(clean_mac) != 12:
        return "Unknown"

    if clean_mac == "000000000000":
        return "Invalid MAC"

    if clean_mac == "FFFFFFFFFFFF":
        return "Broadcast"

    if is_multicast_mac(mac):
        return "Multicast"

    if is_locally_administered_mac(mac):
        return "Private / Randomized"

    prefix = clean_mac[:6]
    vendors = load_oui_database()

    return vendors.get(prefix, "Unknown")


def show_oui_status():
    vendors = load_oui_database()

    if vendors:
        print(
            f"Vendor data  : {len(vendors):,} "
            "OUI assignment(s) loaded"
        )
    else:
        print(
            "Vendor data  : OUI database not found "
            f"({OUI_PATH.name})"
        )


# ---------------------------------------------------------
# Hostname
# ---------------------------------------------------------

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except (
        socket.herror,
        socket.gaierror,
        socket.timeout,
        OSError
    ):
        return ""


# ---------------------------------------------------------
# Scan tracking
# ---------------------------------------------------------

def start_scan(network, local_ip):
    started_at = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scans (
                started_at,
                network,
                local_ip,
                status
            )
            VALUES (?, ?, ?, 'running')
            """,
            (
                started_at,
                str(network),
                local_ip
            )
        )

        return cursor.lastrowid


def complete_scan(
    scan_id,
    active_ips_found,
    devices_identified,
    new_devices_found
):
    completed_at = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scans
            SET
                completed_at = ?,
                active_ips_found = ?,
                devices_identified = ?,
                new_devices_found = ?,
                status = 'completed'
            WHERE id = ?
            """,
            (
                completed_at,
                active_ips_found,
                devices_identified,
                new_devices_found,
                scan_id
            )
        )


def fail_scan(scan_id):
    completed_at = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE scans
            SET
                completed_at = ?,
                status = 'failed'
            WHERE id = ?
            """,
            (
                completed_at,
                scan_id
            )
        )


# ---------------------------------------------------------
# Inventory management
# ---------------------------------------------------------

def mark_all_offline(conn):
    conn.execute(
        """
        UPDATE devices
        SET online = 0
        """
    )


def update_device(conn, ip, mac, hostname):
    now = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    mac = normalize_mac(mac)
    vendor = get_mac_vendor(mac)

    existing = conn.execute(
        """
        SELECT *
        FROM devices
        WHERE mac_address = ?
        """,
        (mac,)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE devices
            SET
                ip_address = ?,
                hostname = ?,
                vendor = ?,
                last_seen = ?,
                times_seen = times_seen + 1,
                online = 1
            WHERE mac_address = ?
            """,
            (
                ip,
                hostname,
                vendor,
                now,
                mac
            )
        )

        return False

    conn.execute(
        """
        INSERT INTO devices (
            mac_address,
            ip_address,
            hostname,
            vendor,
            first_seen,
            last_seen,
            times_seen,
            online
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, 1)
        """,
        (
            mac,
            ip,
            hostname,
            vendor,
            now,
            now
        )
    )

    return True


def add_scan_history(
    conn,
    scan_id,
    ip,
    mac,
    hostname
):
    observed_at = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    conn.execute(
        """
        INSERT INTO scan_history (
            scan_id,
            mac_address,
            ip_address,
            hostname,
            observed_at,
            online
        )
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            scan_id,
            mac,
            ip,
            hostname,
            observed_at
        )
    )


def save_scan(scan_id, active_ips):
    arp_table = get_arp_table()

    discovered = []
    new_devices = []

    with get_connection() as conn:
        mark_all_offline(conn)

        for ip in active_ips:
            mac = arp_table.get(ip)

            # A stable hardware identifier is required before
            # adding the device to the inventory.
            if not mac:
                continue

            mac = normalize_mac(mac)
            hostname = get_hostname(ip)
            vendor = get_mac_vendor(mac)

            is_new = update_device(
                conn,
                ip,
                mac,
                hostname
            )

            add_scan_history(
                conn,
                scan_id,
                ip,
                mac,
                hostname
            )

            device = {
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "vendor": vendor,
                "new": is_new
            }

            discovered.append(device)

            if is_new:
                new_devices.append(device)

    return discovered, new_devices


# ---------------------------------------------------------
# Inventory reporting
# ---------------------------------------------------------

def show_inventory():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ip_address,
                mac_address,
                hostname,
                device_name,
                vendor,
                status,
                online,
                first_seen,
                last_seen,
                times_seen
            FROM devices
            ORDER BY
                online DESC,
                status,
                ip_address
            """
        ).fetchall()

    width = 135

    print()
    print("=" * width)
    print("DEVICE INVENTORY")
    print("=" * width)

    print(
        f"{'IP':<16}"
        f"{'MAC':<19}"
        f"{'Name':<24}"
        f"{'Vendor':<32}"
        f"{'Status':<12}"
        f"{'Online':<9}"
        f"{'Seen':<7}"
    )

    print("-" * width)

    if not rows:
        print("No devices found.")
    else:
        for row in rows:
            name = (
                row["device_name"]
                or row["hostname"]
                or "Unknown"
            )

            vendor = row["vendor"] or "Unknown"
            status = row["status"] or "Unknown"
            online = "YES" if row["online"] else "NO"

            print(
                f"{(row['ip_address'] or ''):<16}"
                f"{row['mac_address']:<19}"
                f"{name[:22]:<24}"
                f"{vendor[:30]:<32}"
                f"{status[:10]:<12}"
                f"{online:<9}"
                f"{row['times_seen']:<7}"
            )

    print("-" * width)
    print(f"Inventory contains {len(rows)} device(s).")


def show_recent_history(limit=20):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                h.observed_at,
                h.scan_id,
                h.ip_address,
                h.mac_address,
                h.hostname,
                d.device_name,
                d.vendor,
                d.status
            FROM scan_history h
            LEFT JOIN devices d
                ON h.mac_address = d.mac_address
            ORDER BY
                h.observed_at DESC,
                h.id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    width = 140

    print()
    print("=" * width)
    print("RECENT SCAN HISTORY")
    print("=" * width)

    print(
        f"{'Scan':<8}"
        f"{'Time':<27}"
        f"{'IP':<16}"
        f"{'MAC':<19}"
        f"{'Device':<24}"
        f"{'Vendor':<32}"
        f"{'Status':<12}"
    )

    print("-" * width)

    if not rows:
        print("No scan history found.")
    else:
        for row in rows:
            name = (
                row["device_name"]
                or row["hostname"]
                or "Unknown"
            )

            vendor = row["vendor"] or "Unknown"
            status = row["status"] or "Unknown"

            print(
                f"{row['scan_id']:<8}"
                f"{row['observed_at']:<27}"
                f"{(row['ip_address'] or ''):<16}"
                f"{row['mac_address']:<19}"
                f"{name[:22]:<24}"
                f"{vendor[:30]:<32}"
                f"{status[:10]:<12}"
            )

    print("-" * width)
    print(f"Showing {len(rows)} recent observation(s).")


# ---------------------------------------------------------
# Scan
# ---------------------------------------------------------

def run_scan():
    initialize_database()

    local_ip = get_local_ip()
    network = get_network(local_ip)

    print()
    print("=" * 70)
    print("NETWATCH")
    print("=" * 70)
    print()
    print(f"This computer : {local_ip}")
    print(f"Scanning      : {network}")

    show_oui_status()

    print()
    print("Looking for devices...")

    scan_id = start_scan(
        network,
        local_ip
    )

    try:
        active_ips = scan_network(network)
        print(f"Active IPs   : {len(active_ips)}")
        
        discovered, new_devices = save_scan(
            scan_id,
            active_ips
        )

        complete_scan(
            scan_id=scan_id,
            active_ips_found=len(active_ips),
            devices_identified=len(discovered),
            new_devices_found=len(new_devices)
        )

    except Exception:
        fail_scan(scan_id)
        raise

    print()
    print(
        f"{len(discovered)} device(s) identified "
        "with IP/MAC information."
    )

    if new_devices:
        print()
        print("=" * 70)
        print("NEW DEVICES")
        print("=" * 70)

        for device in new_devices:
            hostname = (
                device["hostname"]
                or "Unknown"
            )

            vendor = (
                device["vendor"]
                or "Unknown"
            )

            print()
            print(f"IP       : {device['ip']}")
            print(f"MAC      : {device['mac']}")
            print(f"Hostname : {hostname}")
            print(f"Vendor   : {vendor}")

    show_inventory()
    show_recent_history()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        run_scan()

    except KeyboardInterrupt:
        print()
        print("Scan cancelled.")

    except Exception as exc:
        print()
        print(f"ERROR: {exc}")