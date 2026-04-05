"""
Network Scanner — menemukan kamera RTSP di jaringan lokal (LAN).

Scan dilakukan dengan:
1. Deteksi subnet lokal dari interface jaringan
2. Port scan pada port RTSP umum (554, 8554)
3. Test koneksi RTSP dengan OpenCV

Dijalankan dari admin panel tanpa perlu tool eksternal.
"""

import socket
import struct
import threading
import time
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

# Common RTSP ports
RTSP_PORTS = [554, 8554, 8080, 80]

# Common RTSP URL paths to try
RTSP_PATHS = [
    "/",
    "/live",
    "/live/ch00_0",
    "/live/ch01_0",
    "/stream1",
    "/stream",
    "/cam/realmonitor",
    "/h264",
    "/Streaming/Channels/101",
    "/Streaming/Channels/1",
    "/video1",
    "/MediaInput/h264",
    "/onvif1",
    "/1",
]


def get_local_subnets() -> List[str]:
    """
    Detect local network subnets from active interfaces.
    Returns list of CIDR strings like ["192.168.1.0/24"].
    """
    subnets = set()

    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    ip = addr_info.get("addr")
                    netmask = addr_info.get("netmask")
                    if ip and netmask and not ip.startswith("127."):
                        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                        subnets.add(str(network))
    except ImportError:
        # Fallback: use socket to get local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            # Assume /24 subnet
            parts = local_ip.split(".")
            subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            subnets.add(subnet)
        except Exception:
            pass

    return sorted(subnets)


def _check_port(ip: str, port: int, timeout: float = 0.8) -> bool:
    """Check if a TCP port is open on the given IP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _test_rtsp_url(url: str, timeout: float = 3.0) -> Optional[dict]:
    """Test if an RTSP URL is accessible via OpenCV."""
    try:
        import cv2
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|analyzeduration;1000000|probesize;1000000"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            return None

        start = time.time()
        ret = False
        while time.time() - start < timeout:
            ret, frame = cap.read()
            if ret:
                break
            time.sleep(0.1)

        if ret:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            return {"url": url, "resolution": [w, h], "accessible": True}

        cap.release()
        return None
    except Exception:
        return None


def scan_network(
    subnet: Optional[str] = None,
    ports: Optional[List[int]] = None,
    max_workers: int = 50,
    port_timeout: float = 0.8,
    progress_callback=None,
) -> List[dict]:
    """
    Scan a network subnet for RTSP cameras.

    Args:
        subnet: CIDR notation like "192.168.1.0/24". Auto-detects if None.
        ports: List of ports to scan. Defaults to RTSP_PORTS.
        max_workers: Number of concurrent threads for scanning.
        port_timeout: Timeout per port check in seconds.
        progress_callback: Optional callback(current, total) for progress.

    Returns:
        List of discovered cameras with their RTSP URLs.
    """
    if ports is None:
        ports = RTSP_PORTS

    # Auto-detect subnet if not provided
    if subnet is None:
        detected = get_local_subnets()
        if not detected:
            return []
        subnet = detected[0]

    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
    except ValueError:
        return []

    hosts = [str(ip) for ip in network.hosts()]
    total_checks = len(hosts) * len(ports)
    checked = 0

    # Phase 1: Port scan to find hosts with open RTSP ports
    open_hosts = []  # [(ip, port), ...]

    def check_host_port(ip, port):
        return (ip, port, _check_port(ip, port, port_timeout))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for ip in hosts:
            for port in ports:
                futures.append(executor.submit(check_host_port, ip, port))

        for future in as_completed(futures):
            checked += 1
            if progress_callback and checked % 50 == 0:
                progress_callback(checked, total_checks)
            try:
                ip, port, is_open = future.result()
                if is_open:
                    open_hosts.append((ip, port))
            except Exception:
                continue

    # Phase 2: Test RTSP URLs on discovered hosts
    discovered = []

    for ip, port in open_hosts:
        # Try common RTSP paths
        found_any = False
        urls_to_try = [f"rtsp://{ip}:{port}{path}" for path in RTSP_PATHS[:5]]

        for url in urls_to_try:
            result = _test_rtsp_url(url, timeout=3.0)
            if result:
                discovered.append({
                    "ip": ip,
                    "port": port,
                    "url": result["url"],
                    "resolution": result["resolution"],
                    "status": "accessible",
                })
                found_any = True
                break  # One working URL per host:port is enough

        if not found_any:
            # Port is open but couldn't get RTSP stream — still report it
            discovered.append({
                "ip": ip,
                "port": port,
                "url": f"rtsp://{ip}:{port}/",
                "resolution": None,
                "status": "port_open",
            })

    # Sort by IP
    discovered.sort(key=lambda x: (x["ip"], x["port"]))
    return discovered


def quick_rtsp_test(url: str) -> dict:
    """Quick test a single RTSP URL. Returns status info."""
    result = _test_rtsp_url(url, timeout=5.0)
    if result:
        return {
            "ok": True,
            "url": result["url"],
            "resolution": result["resolution"],
        }
    return {
        "ok": False,
        "url": url,
        "error": "Tidak dapat mengakses stream RTSP",
    }
