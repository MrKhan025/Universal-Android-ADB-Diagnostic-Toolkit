from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set

# Critical core Android/OEM packages that must never be disabled or uninstalled
# as bloatware because doing so breaks boot, system UI, telephony, or app store functionality.
PROTECTED_PACKAGES: Set[str] = {
    "android",
    "com.android.vending",
    "com.android.systemui",
    "com.android.settings",
    "com.android.phone",
    "com.android.providers.settings",
    "com.android.providers.telephony",
    "com.android.providers.contacts",
    "com.android.providers.media",
    "com.android.shell",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.google.android.packageinstaller",
    "com.google.android.permissioncontroller",
    "com.huawei.hwid",
}

OEM_BLOATWARE: Dict[str, List[str]] = {
    "google": [
        "com.google.android.apps.messaging",
        "com.google.android.apps.translate",
        "com.google.android.apps.wellbeing",
        "com.google.android.apps.tachyon",
        "com.google.android.apps.magazines",
        "com.google.android.apps.podcasts",
        "com.google.android.videos",
        "com.google.android.music",
        "com.google.android.feedback",
    ],
    "samsung": [
        "com.samsung.android.app.watchmanager",
        "com.samsung.android.messaging",
        "com.samsung.android.oneconnect",
        "com.samsung.android.bixby.agent",
        "com.samsung.android.app.spage",
        "com.samsung.android.game.gamehome",
        "com.samsung.android.game.gametools",
        "com.samsung.android.aremoji",
        "com.samsung.android.kidsinstaller",
    ],
    "xiaomi": [
        "com.miui.cleanmaster",
        "com.xiaomi.mipicks",
        "com.miui.miservice",
        "com.miui.analytics",
        "com.miui.msa.global",
        "com.miui.Compass",
        "com.xiaomi.glgm",
        "com.miui.videoplayer",
        "com.miui.player",
    ],
    "huawei": [
        "com.huawei.android.hsf",
        "com.huawei.android.thememanager",
        "com.huawei.himovie.overseas",
        "com.huawei.health",
        "com.huawei.phoneservice",
        "com.huawei.appmarket",
    ],
    "oneplus": [
        "com.oneplus.mms",
        "com.oneplus.opbugreport",
        "com.oneplus.LogKit",
        "com.oneplus.brickmode",
        "net.oneplus.forums",
    ],
    "carrier": [
        "com.google.android.apps.nbu.files",
        "com.facebook.system",
        "com.facebook.appmanager",
        "com.facebook.services",
        "com.facebook.katana",
        "com.Netflix.mediaclient",
        "com.spotify.music",
    ],
}


def is_protected_package(package: str) -> bool:
    """Return True if the package is a critical core system package that must not be removed."""
    return package.strip() in PROTECTED_PACKAGES


def get_safe_bloatware_packages() -> Dict[str, List[str]]:
    """Return a copy of the curated OEM safe-debloat package catalog."""
    return {oem: list(pkgs) for oem, pkgs in OEM_BLOATWARE.items()}


def safe_removal_candidates(
    serial: Optional[str] = None,
    package_list: Optional[Iterable[str]] = None,
) -> List[str]:
    """Return sorted bloatware candidates installed on the target device or within package_list.

    If `package_list` is omitted and `serial` is provided, installed packages are queried
    from the connected device via ADB. Protected system packages are strictly excluded.
    """
    if package_list is None:
        if serial:
            from .cli import list_packages

            installed_set = set(list_packages(serial, third_party_only=False))
        else:
            installed_set = set()
    else:
        installed_set = {pkg.strip() for pkg in package_list if pkg and pkg.strip()}

    if not installed_set:
        return []

    candidate_set: Set[str] = set()
    for _, packages in OEM_BLOATWARE.items():
        for package in packages:
            if package in installed_set and not is_protected_package(package):
                candidate_set.add(package)
    return sorted(candidate_set)


def categorize_bloatware_candidates(
    serial: Optional[str] = None,
    package_list: Optional[Iterable[str]] = None,
) -> Dict[str, List[str]]:
    """Group detected safe-removal candidates by their OEM/category."""
    candidates = set(safe_removal_candidates(serial=serial, package_list=package_list))
    grouped: Dict[str, List[str]] = {}
    for category, packages in OEM_BLOATWARE.items():
        matched = sorted(pkg for pkg in packages if pkg in candidates)
        if matched:
            grouped[category] = matched
    return grouped
