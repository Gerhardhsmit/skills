#!/usr/bin/env python3
"""Write an engine draft as an .eml for the existing CTTX Outlook loader (stdlib only).

The loader is "Load CTTX Drafts" (outbound-communication/load_drafts.py in
Gerhardhsmit/cttx-infrastructure-intelligence). It loads .eml files from
Desktop\\CTTX Prospect Drafts into gerhard@cttx.co.za -> Drafts and never sends.
Attachments travel in the "X-CTTX-Attach" header, relative to the .eml's folder.

  python3 write_eml.py draft.json --out <folder>
draft.json: {"to","subject","body","attachments":[...],"prospect","contact_name","email_status"}
"""
import argparse
import datetime as dt
import json
import re
import sys
from email.message import EmailMessage
from pathlib import Path


def eml_name(prospect, contact_name, date=None):
    date = date or dt.date.today()
    who = re.sub(r"[^A-Za-z0-9]+", "_", contact_name or "Director").strip("_")
    return f"{prospect} - DRAFT_{who}_Assessment_{date:%Y%m%d}.eml"


def build(draft):
    msg = EmailMessage()
    msg["From"] = "gerhard@cttx.co.za"
    msg["To"] = draft["to"]
    subject = draft["subject"]
    if draft.get("email_status") == "INFERRED":
        subject = "[VERIFY ADDRESS] " + subject
    msg["Subject"] = subject
    msg["X-Unsent"] = "1"
    if draft.get("attachments"):
        msg["X-CTTX-Attach"] = ", ".join(draft["attachments"])
    msg.set_content(draft["body"])
    return msg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", default=".")
    a = ap.parse_args(argv)
    d = json.load(open(a.draft))
    out = Path(a.out) / eml_name(d["prospect"], d.get("contact_name"))
    out.write_bytes(bytes(build(d)))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
