from __future__ import annotations

from typing import Dict, List, Set

OEM_BLOATWARE = {
    "google": [
        "com.google.android.apps.messaging",
        "com.google.android.apps.translate",
        "com.google.android.apps.wellbeing",
    ],
    "samsung": [
        "com.samsung.android.app.watchmanager",
        "com.samsung.android.messaging",
        "com.samsung.android.oneconnect",
    ],
    "xiaomi": [
        "com.miui.cleanmaster",
        "com.xiaomi.mipicks",
        "com.miui.miservice",
    ],
    "huawei": [
        "com.huawei.android.hsf",
        "com.huawei.hwid",
        "com.huawei.android.thememanager",
    ],
    "oneplus": [
        "com.oneplus.mms",
        "com.oneplus.opbugreport",
    ],
    "carrier": [
        "com.android.vending",
        "com.google.android.apps.nbu.files",
    ],
}


def get_safe_bloatware_packages() -> Dict[str, List[str]]:
    return OEM_BLOATWARE


def safe_removal_candidates(serial: str | None = None, package_list: List[str] | None = None) -> List[str]:
    installed = package_list or []
    candidate_set: Set[str] = set()
    for _, packages in OEM_BLOATWARE.items():
        for package in packages:
            if package in installed:
                candidate_set.add(package)
    return sorted(candidate_set)
