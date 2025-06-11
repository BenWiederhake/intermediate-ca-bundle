#!/usr/bin/env python3

# This is a bare-bones half-assed re-implementation of kinto.
# I did this because it seems that all kinto clients out there don't properly support attachments,
# and if I have to manually download all the files anyway, then I can also just go the direct route.

import hashlib
import json
import os
import requests
import time


# === CONFIG ===
# Feel free to change these values as you see fit.

# Things that shouldn't appear in git. See file "secret_config_template.py".
from secret_config import CRAWLER_CONTACT_EMAIL
# URL to query. Taken from https://blog.mozilla.org/security/2020/11/13/preloading-intermediate-ca-certificates-into-firefox/
URL_RECORDS = "https://firefox.settings.services.mozilla.com/v1/buckets/security-state/collections/intermediates/records/"
# Where should the certs be dumped? Directory must exist already. Files might be overwritten! Must end with slash!
DESTINATION_DIR = "intermediate_certs/"


# === IMPLICIT CONFIG ===
# You really shouldn't need to touch these.

# In theory, the server at `URL_RECORDS` should be queried with the bare-bones URL (cut off after "v1").
# Then, we would look at the JSON response, specifically:
#   json_parsed_response_object.capabilities.attachments.base_url = "https://firefox-settings-attachments.cdn.mozilla.net/"
# … but I guess we can skip that step, since the result SHOULD always be the same.
# Must end with a slash!
URL_BASE_ATTACHMENTS = "https://firefox-settings-attachments.cdn.mozilla.net/"
# Make it easier to be contacted if the crawler does something bad.
# "CowBirdTacitFlower" has zero results on Google as of 2023-10-22.
USER_AGENT = f"intermediates_crawler/0.0.1 (contact: {CRAWLER_CONTACT_EMAIL}) (codename: CowBirdTacitFlower)"
REQUEST_HEADERS = {"user-agent": USER_AGENT}
# The resulting file can be used as input to libcurl, e.g. CURLOPT_CAINFO_BLOB.
FILENAME_CAINFO_BLOB = f"{DESTINATION_DIR}/intermediate_certs.pem"
# That might be interesting, so also write it out.
FILENAME_RECORDS = f"{DESTINATION_DIR}/records.json"


def get_buffered(url, filename, expected_size=None, expected_hash=None):
    assert (expected_size is None) == (expected_hash is None)
    print(f"Fetching {url} …")
    data = None
    cached = False
    if os.path.exists(filename) and expected_size is not None:
        print(f"  … trying cached file {filename} …")
        with open(filename, "rb") as fp:
            data = fp.read()
        actual_hash = hashlib.sha256(data).hexdigest()
        if len(data) != expected_size:
            print(f"    … but size mismatch: expected={expected_size}, actual={len(data)}")
        elif actual_hash.lower() != expected_hash.lower():
            print(f"    … but hash mismatch(?!): expected={expected_hash}, actual={actual_hash}")
        else:
            print(f"    … hit!")
            cached = True
    if not cached:
        print(f"  … from server")
        time.sleep(3)
        data = requests.get(url, headers=REQUEST_HEADERS).content
        actual_hash = hashlib.sha256(data).hexdigest()
        if expected_size is not None and len(data) != expected_size:
            print(f"    … but size mismatch: expected={expected_size}, actual={len(data)}")
            raise AssertionError(f"server doesn't like me, better abort")
        elif expected_hash is not None and actual_hash.lower() != expected_hash.lower():
            print(f"    … but hash mismatch(?!): expected={expected_hash}, actual={actual_hash}")
            raise AssertionError(f"server doesn't like me, better abort")
        print(f"  … saving as {filename}")
        with open(filename, "wb") as fp:
            fp.write(data)
    return data


def fetch_record_list():
    return get_buffered(URL_RECORDS, FILENAME_RECORDS)


def fetch_record_attachment(record):
    # Excerpt from `gron records.json`:
    # json.data[0].attachment.filename = "9VZ7Yd685RTXsE6rL_puuMbnejYaXwaZasGL7c-Uolc=.pem";
    # json.data[0].attachment.hash = "6915db4e2c315f0ef561152eb43c24a83ff0b2a53b17f99b0016401498bd9a2d";
    # json.data[0].attachment.location = "security-state-staging/intermediates/47927f74-196f-42a4-a2a8-51f6c9298cd2.pem";
    # json.data[0].attachment.size = 2060;
    attachment = record["attachment"]
    url = URL_BASE_ATTACHMENTS + attachment["location"]
    filename = DESTINATION_DIR + attachment["filename"]
    return get_buffered(url, filename, attachment["size"], attachment["hash"])


def fetch_newest_records(records):
    pems = []
    for record in records:
        pems.append(fetch_record_attachment(record))
    return pems


def run():
    records_bytes = fetch_record_list()
    records = json.loads(records_bytes)
    pems = fetch_newest_records(records["data"])
    print(f"Writing all {len(pems)} records to {FILENAME_CAINFO_BLOB} …")
    # We only start writing once all pems are fetched.
    # This way, the file is "never" in an inconsistent state.
    
    with open(FILENAME_CAINFO_BLOB, "wb") as fp:
        for pem in pems:
            fp.write(pem)
            fp.write(b'\n')
    print(f"Done! {FILENAME_CAINFO_BLOB} is ready to be used.")


if __name__ == "__main__":
    run()
