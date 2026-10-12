#!/usr/bin/env python3

import json
import plistlib
import sys
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile


def update_source(source_path, release, ipa_directory):
    with source_path.open() as source_file:
        source = json.load(source_file)

    assets = [asset for asset in release["assets"] if asset["name"].lower().endswith(".ipa")]
    if len(assets) != 1:
        raise ValueError("The release must contain exactly one IPA asset.")

    asset = assets[0]
    ipa_path = ipa_directory / asset["name"]
    with ZipFile(ipa_path) as ipa:
        info_paths = [name for name in ipa.namelist() if name.startswith("Payload/") and name.count("/") == 2 and name.endswith(".app/Info.plist")]
        if len(info_paths) != 1:
            raise ValueError("The IPA must contain exactly one app Info.plist.")
        info = plistlib.loads(ipa.read(info_paths[0]))

    app = next((app for app in source["apps"] if app["bundleIdentifier"] == info["CFBundleIdentifier"]), None)
    if app is None:
        raise ValueError(f"No source app matches {info['CFBundleIdentifier']}.")

    version = info["CFBundleShortVersionString"]
    if release["tag_name"].removeprefix("v") != version:
        raise ValueError(f"Release tag {release['tag_name']} does not match IPA version {version}.")
    if asset["size"] != ipa_path.stat().st_size:
        raise ValueError("The release asset size does not match the IPA.")

    entry = {
        "version": version,
        "buildVersion": info["CFBundleVersion"],
        "date": datetime.fromisoformat(release["published_at"].replace("Z", "+00:00")).date().isoformat(),
        "localizedDescription": (release.get("body") or "No release notes provided.").replace("\r\n", "\n").strip(),
        "downloadURL": asset["browser_download_url"],
        "size": asset["size"],
        "minOSVersion": info["MinimumOSVersion"],
    }

    versions = app["versions"]
    for index, existing in enumerate(versions):
        if existing["version"] == version and existing.get("buildVersion") == entry["buildVersion"]:
            if existing == entry:
                return False
            versions[index] = entry
            break
    else:
        versions.insert(0, entry)

    with source_path.open("w") as source_file:
        json.dump(source, source_file, indent=2)
        source_file.write("\n")
    return True


def main():
    source_path = Path(sys.argv[1])
    with Path(sys.argv[2]).open() as event_file:
        release = json.load(event_file)["release"]
    if update_source(source_path, release, Path(sys.argv[3])):
        print(f"Updated AltStore source for {release['tag_name']}.")
    else:
        print(f"AltStore source already contains {release['tag_name']}.")


if __name__ == "__main__":
    main()
