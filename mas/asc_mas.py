#!/usr/bin/env python3
"""asc_mas.py - App Store Connect API (key from the repo secrets) for the Mac App Store build.

  asc_mas.py signing <out dir>      creates a new private key + CSR on the runner, the two Mac App Store certificates
                                    (MAC_APP_DISTRIBUTION, MAC_INSTALLER_DISTRIBUTION) and a MAC_APP_STORE provisioning
                                    profile for com.xrero.office. Older Mac App Store certificates are revoked first
                                    (revoking does not affect apps already published). Writes key.pem, app.cer,
                                    installer.cer, profile.provisionprofile, team.txt.
  asc_mas.py macos-version <ver>    makes sure the Xrero Office app record has a macOS App Store version (= "Add Platform
                                    > macOS"); prints its state.
Env: ASC_KEY (p8 text), ASC_KEY_ID, ASC_ISSUER. Nothing secret is printed.
"""
import base64, json, os, sys, time, urllib.error, urllib.request

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

BUNDLE = "com.xrero.office"
APP_ID = "6819063639"          # Xrero Office in App Store Connect
API = "https://api.appstoreconnect.apple.com"


def token():
    now = int(time.time())
    return jwt.encode({"iss": os.environ["ASC_ISSUER"], "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      os.environ["ASC_KEY"], algorithm="ES256", headers={"kid": os.environ["ASC_KEY_ID"], "typ": "JWT"})


def call(method, path, body=None, ok=(200, 201, 204)):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if e.code in ok:
            return {}
        raise SystemExit("ASC %s %s -> %s %s" % (method, path, e.code, detail[:1500]))


def bundle_id():
    r = call("GET", "/v1/bundleIds?filter[identifier]=%s&limit=20" % BUNDLE)
    rows = [d for d in r.get("data", []) if d["attributes"]["identifier"] == BUNDLE]
    if not rows:
        raise SystemExit("bundle id %s not found in the developer account" % BUNDLE)
    b = rows[0]
    print("bundleId:", b["id"], "platform:", b["attributes"]["platform"], "seedId(team):", b["attributes"]["seedId"])
    return b


def signing(out):
    os.makedirs(out, exist_ok=True)
    b = bundle_id()
    team = b["attributes"]["seedId"]
    open(os.path.join(out, "team.txt"), "w").write(team)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    open(os.path.join(out, "key.pem"), "wb").write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Xrero Mac App Store CI"),
        x509.NameAttribute(NameOID.EMAIL_ADDRESS, "info@xrero.com"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "AE")])).sign(key, hashes.SHA256())
    csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()

    certs = {}
    for ctype, fname in (("MAC_APP_DISTRIBUTION", "app.cer"), ("MAC_INSTALLER_DISTRIBUTION", "installer.cer")):
        old = call("GET", "/v1/certificates?filter[certificateType]=%s&limit=50" % ctype).get("data", [])
        for c in old:
            call("DELETE", "/v1/certificates/%s" % c["id"])
            print("revoked old", ctype, c["attributes"].get("name"), c["attributes"].get("expirationDate"))
        r = call("POST", "/v1/certificates", {"data": {"type": "certificates", "attributes": {
            "certificateType": ctype, "csrContent": csr_pem}}})
        d = r["data"]
        open(os.path.join(out, fname), "wb").write(base64.b64decode(d["attributes"]["certificateContent"]))
        certs[ctype] = d["id"]
        print("created", ctype, d["attributes"].get("name"), "expires", d["attributes"].get("expirationDate"))

    name = "Xrero Office Mac App Store (CI)"
    for pr in call("GET", "/v1/profiles?filter[name]=%s&limit=50" % urllib.request.quote(name)).get("data", []):
        call("DELETE", "/v1/profiles/%s" % pr["id"])
        print("deleted old profile", pr["id"])
    r = call("POST", "/v1/profiles", {"data": {"type": "profiles",
        "attributes": {"name": name, "profileType": "MAC_APP_STORE"},
        "relationships": {"bundleId": {"data": {"type": "bundleIds", "id": b["id"]}},
                          "certificates": {"data": [{"type": "certificates", "id": certs["MAC_APP_DISTRIBUTION"]}]}}}})
    a = r["data"]["attributes"]
    open(os.path.join(out, "profile.provisionprofile"), "wb").write(base64.b64decode(a["profileContent"]))
    print("profile", a["name"], a["profileType"], a["profileState"], "expires", a["expirationDate"])


def macos_version(ver):
    vs = call("GET", "/v1/apps/%s/appStoreVersions?filter[platform]=MAC_OS&limit=10" % APP_ID).get("data", [])
    if vs:
        for v in vs:
            print("macOS version:", v["attributes"]["versionString"], v["attributes"]["appStoreState"])
        return
    r = call("POST", "/v1/appStoreVersions", {"data": {"type": "appStoreVersions",
        "attributes": {"platform": "MAC_OS", "versionString": ver, "releaseType": "AFTER_APPROVAL"},
        "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}})
    print("created macOS version", r["data"]["attributes"]["versionString"], r["data"]["attributes"]["appStoreState"])


if __name__ == "__main__":
    if sys.argv[1] == "signing":
        signing(sys.argv[2])
    elif sys.argv[1] == "macos-version":
        macos_version(sys.argv[2])
    else:
        raise SystemExit(__doc__)
