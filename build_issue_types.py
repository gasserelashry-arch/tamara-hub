#!/usr/bin/env python3
"""Build official Issue Type paths from the ISSUE TYPES Google Doc structure."""
from __future__ import annotations

import json
from pathlib import Path

# Category > Sub-Category > [leaf issue types] from the shared doc + comments
TAXONOMY = {
    "Account": {
        "Account Security": [
            "Data Security & Privacy",
            "National ID Fraud",
            "Unrecognized Login",
        ],
        "Authentication": [
            "MFA - General inquiry",
            "MFA - Verification Failure",
            "MFA - Add / remove trusted device",
        ],
        "Due Date Preference": [
            "General Inquiries",
            "Tech/Missing email or SMS",
            "Tech/Opt-out or lock issue",
            "Tech/Preference not saved",
            "Tech/Wrong due date on new order",
            "N/A",
        ],
        "N/A": [
            "ID verification",
            "N/A",
            "Passcode",
            "Registration & login",
            "About Tamara (General)",
            "About Tamara Smart Membership & Benefits",
            "Campaign Post",
            "Card Usage, Eligibility & Benefits",
            "Cashback",
            "Chargeback",
            "Contact from merchant",
            "Could not find a relevant issue type",
            "Customer feedback about merchant",
            "Customer Processing Fees",
            "Discount",
            "Fraudulent / Misleading Ads",
            "High Downpayment",
            "How to return or cancel an order or item",
            "How to subscribe",
            "How to unsubscribe",
            "Incorrect refund amount",
            "Late fee",
            "Merchant fraud",
            "Merchant incorrectly canceled the order / item",
            "Other",
            "Postpone payment",
            "Refund Blocked by Merchant",
            "Related to Collection agency",
            "Shariah compliance",
            "Spam",
            "Statement",
            "Tamara Card Cashback amount incorrect",
            "Tamara Card Cashback not received",
            "Tamara Card fees",
            "Unable to pay pending dues",
            "Wallet refund",
        ],
        "Registration & login": [
            "Didn't receive the login / registration OTP",
            "Phone number already in use",
        ],
        "Tamara Health": [
            "General Inquiry",
            "Grade or Pillar Issue",
            "Technical Issue",
            "N/A",
        ],
        "Update Account": [
            "Change Email",
            "Change phone number",
            "Delete account",
            "Reactivate account",
        ],
    },
    "Legal and Government": {
        "Credit Bureau": [
            "Credit Bureau Process & Report",
            "Delayed Report",
            "Disputed-Order Related Reporting",
            "Fraudulent Bureau Entry",
            "General Inquiries",
            "Incorrect Reporting",
            "Inquiry Update (UAE)",
        ],
        "N/A": ["Shariah compliance"],
    },
    "Order": {
        "Dispute": [
            "Cancel dispute",
            "Canceled by merchant but not reflected in Tamara",
            "Item not as described",
            "Item or order not delivered",
            "Return/cancellation not processed",
        ],
        "Merchant Fraud": ["Extra Fees"],
        "Murabha - Pay By Finance": [
            "Early Settlement",
            "Profit Rates",
            "Required Documents",
            "Eligibility & Inquiries",
            "Signed contract",
        ],
        "N/A": [
            "N/A",
            "Merchant Fraud",
            "About Tamara (General)",
            "About Tamara Smart Membership & Benefits",
            "Campaign Post",
            "Card Usage, Eligibility & Benefits",
            "Cashback",
            "Chargeback",
            "Contact from merchant",
            "Could not find a relevant issue type",
            "Customer feedback about merchant",
            "Customer Processing Fees",
            "Discount",
            "Fraudulent / Misleading Ads",
            "High Downpayment",
            "How to return or cancel an order or item",
            "How to subscribe",
            "How to unsubscribe",
            "ID verification",
            "Incorrect refund amount",
            "Late fee",
            "Merchant fraud",
            "Merchant incorrectly canceled the order / item",
            "Other",
            "Passcode",
            "Postpone payment",
            "Refund Blocked by Merchant",
            "Registration & login",
            "Related to Collection agency",
            "Shariah compliance",
            "Spam",
            "Statement",
            "Tamara Card Cashback amount incorrect",
            "Tamara Card Cashback not received",
            "Tamara Card fees",
            "Unable to pay pending dues",
            "Wallet refund",
        ],
        "Placing an Order": [
            "Can't see a specific split payment option (SiX)",
            "Can't see split payment options (only PIF)",
            "Can't see Tamara as a payment option",
            "Cannot see order (expired order)",
            "Cannot see order (stuck order)",
            "Chose the wrong installment plan",
            "Declined order",
            "Didn't receive the order OTP",
            "Instore - did not receive the payment link SMS",
            "Link Bank Account",
            "Maximum / minimum purchase limit",
            "Order verification IVR call",
            "Pay Next Month",
        ],
    },
    "Other": {
        "Dispute": [
            "Cancel dispute",
            "Canceled by merchant but not reflected in Tamara",
            "Item not as described",
            "Item or order not delivered",
            "Return/cancellation not processed",
        ],
        "Feedback": [
            "Feedback about Tamara",
            "New feature or product request",
            "New merchant request",
        ],
        "Incomplete Contact": [
            "Authentication failed",
            "Call/chat connection issue",
            "Call/chat dropped",
            "Dropped by Agent (Profanity)",
            "No response from customer",
        ],
        "Murabha - Pay By Finance": [
            "Early Settlement",
            "Profit Rates",
            "Required Documents",
        ],
        "N/A": [
            "About Tamara (General)",
            "About Tamara Smart Membership & Benefits",
            "Campaign Post",
            "Card Usage, Eligibility & Benefits",
            "Cashback",
            "Chargeback",
            "Contact from merchant",
            "Could not find a relevant issue type",
            "Customer feedback about merchant",
            "Customer Processing Fees",
            "Discount",
            "Dispute",
            "Fraudulent / Misleading Ads",
            "High Downpayment",
            "How to return or cancel an order or item",
            "How to subscribe",
            "How to unsubscribe",
            "ID verification",
            "Incorrect refund amount",
            "Late fee",
            "Merchant fraud",
            "Merchant incorrectly canceled the order / item",
            "Murabha - Pay By Finance",
            "N/A",
            "Other",
            "Outbound",
            "Passcode",
            "Placing an Order",
            "Postpone payment",
            "Refund Blocked by Merchant",
            "Registration & login",
            "Related to Collection agency",
            "Shariah compliance",
            "Spam",
            "Statement",
            "Tamara Card Cashback amount incorrect",
            "Tamara Card Cashback not received",
            "Tamara Card fees",
            "Test contact",
            "Unable to pay pending dues",
            "Wallet refund",
        ],
        "Outbound": ["Outbound calling campaign"],
        "Placing an Order": [
            "Can't see a specific split payment option (SiX)",
            "Can't see split payment options (only PIF)",
            "Can't see Tamara as a payment option",
            "Cannot see order (expired order)",
            "Cannot see order (stuck order)",
            "Chose the wrong installment plan",
            "Declined order",
            "Didn't receive the order OTP",
            "Instore - did not receive the payment link SMS",
            "Link Bank Account",
            "Maximum / minimum purchase limit",
            "Order verification IVR call",
        ],
        "Vulnerable Customer": [
            "Customer with total financial disability",
            "Customer with total physical disability",
            "Deceased Customer Case",
        ],
        "About Tamara (General)": ["Tamara's Wallet"],
    },
    "Payment": {
        "Autocharge": [
            "Autocharge Amount",
            "Autocharge card",
            "Autocharge date",
            "Other",
        ],
        "Murabha - Pay By Finance": [
            "Early Settlement",
            "Profit Rates",
            "Required Documents",
        ],
        "N/A": [
            "Autocharge",
            "Collection Process",
            "Customer Processing Fees (CPF)",
            "Early Settlement",
            "Murabha - Pay By Finance",
            "N/A",
            "Unable to Pay Pending Dues",
            "Unrecorded charges",
            "Voided payment",
        ],
        "Payment Methods": [
            "Card is not accepted",
            "How to add/remove a card",
            "Supported Cards",
            "Payment Link",
        ],
        "Voided payment": [
            "Other voided payment issue",
            "Void failed",
            "Void succeeded - no issue",
        ],
        "Unrecognized charge": [
            "Duplicate charge",
            "Explained to customer (no issue)",
            "Suspected fraud",
        ],
        "Unrecorded charges": [
            "Other unrecorded charge issues",
            "Payment authorization failed",
            "Payment not reflected",
        ],
    },
    "Promotions & Cashback": {
        "N/A": ["N/A"],
    },
    "Refunds and Cancellations": {
        "Late Refund": [
            "Refund already processed",
            "Refund failed",
            "Refund not processed",
        ],
        "N/A": [
            "How to return or cancel an order or item",
            "Merchant unable to process refund",
            "N/A",
            "Refunds and Cancellations",
        ],
    },
    "Smart Membership": {
        "Invoice & Statements": ["Snooze Statement"],
        "N/A": ["N/A"],
    },
    "Tamara Card": {
        "N/A": ["N/A", "Tamara Card Management"],
        "Tamara Card Management": [
            "Apple Pay / Google Pay",
            "Cannot Activate Tamara Card",
            "Cannot View Tamara Card Details",
            "Deactivate Tamara Card",
            "Report Lost or Stolen Device",
        ],
        "Tamara Card Payment": [
            "Other Tamara Card payment related issues",
            "Tamara Card Chargeback - Disputes",
            "Tamara Card OTP not received",
            "Tamara Card Refund Not Received",
            "Tamara Card Transaction Declined",
            "Unauthorized Charge",
        ],
    },
    "Lavender Membership": {
        "Lavender Membership": [
            "About Tamara Lavender Membership Eligibility & Benefits",
            "Lavender Membership",
        ],
        "N/A": ["Lavender Membership"],
    },
}


def build_paths():
    paths = []
    for cat, subs in TAXONOMY.items():
        for sub, leaves in subs.items():
            for leaf in leaves:
                paths.append(f"{cat} > {sub} > {leaf}")
    # de-dupe preserve order
    seen = set()
    out = []
    for p in paths:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    out.sort(key=lambda s: s.lower())
    return out


if __name__ == "__main__":
    paths = build_paths()
    out = Path(__file__).with_name("official_issue_types.json")
    out.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(paths)} issue types -> {out}")
