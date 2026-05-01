#!/usr/bin/env python3
"""
Extract X (Twitter) authentication cookies from browser or manual input.

This script helps extract the auth_token and ct0 cookies needed to authenticate
with the X API using the reverse-engineered GraphQL endpoint.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    import browser_cookie3
    HAS_BROWSER_COOKIE3 = True
except ImportError:
    HAS_BROWSER_COOKIE3 = False


def extract_from_chrome() -> dict:
    """
    Extract X auth cookies from Chrome browser.
    
    Returns:
        dict with auth_token and ct0 keys, or empty dict on failure
    """
    if not HAS_BROWSER_COOKIE3:
        print("Error: browser_cookie3 not installed. Install with: pip install browser-cookie3")
        return {}
    
    try:
        print("Attempting to extract cookies from Chrome...")
        cj = browser_cookie3.chrome(domain_name="twitter.com")
        cookies = {cookie.name: cookie.value for cookie in cj}
        
        result = {}
        if "auth_token" in cookies:
            result["auth_token"] = cookies["auth_token"]
        if "ct0" in cookies:
            result["ct0"] = cookies["ct0"]
        
        if result:
            print("✓ Successfully extracted cookies from Chrome")
            return result
        else:
            print("✗ Could not find auth_token or ct0 in Chrome cookies")
            return {}
    except Exception as e:
        print(f"✗ Failed to extract from Chrome: {e}")
        return {}


def extract_from_firefox() -> dict:
    """
    Extract X auth cookies from Firefox browser.
    
    Returns:
        dict with auth_token and ct0 keys, or empty dict on failure
    """
    if not HAS_BROWSER_COOKIE3:
        print("Error: browser_cookie3 not installed. Install with: pip install browser-cookie3")
        return {}
    
    try:
        print("Attempting to extract cookies from Firefox...")
        cj = browser_cookie3.firefox(domain_name="twitter.com")
        cookies = {cookie.name: cookie.value for cookie in cj}
        
        result = {}
        if "auth_token" in cookies:
            result["auth_token"] = cookies["auth_token"]
        if "ct0" in cookies:
            result["ct0"] = cookies["ct0"]
        
        if result:
            print("✓ Successfully extracted cookies from Firefox")
            return result
        else:
            print("✗ Could not find auth_token or ct0 in Firefox cookies")
            return {}
    except Exception as e:
        print(f"✗ Failed to extract from Firefox: {e}")
        return {}


def manual_input() -> dict:
    """
    Manually prompt user to input X auth cookies.
    
    Returns:
        dict with auth_token and ct0 keys, or empty dict on failure
    """
    print("\n" + "="*70)
    print("MANUAL COOKIE EXTRACTION INSTRUCTIONS")
    print("="*70)
    print("""
To extract your X authentication cookies:

1. Open X (twitter.com) in your browser
2. Open Developer Tools (F12 or Ctrl+Shift+I)
3. Go to the "Application" or "Storage" tab
4. Click on "Cookies" in the left sidebar
5. Select "https://twitter.com" 
6. Look for the following cookies:
   - auth_token: A long alphanumeric string (40+ characters)
   - ct0: Another long string (160+ characters)
7. Copy each value and paste below when prompted

NOTE: These cookies authenticate API requests. Keep them SECRET!
Do not share them with anyone else.
""")
    print("="*70 + "\n")
    
    while True:
        auth_token = input("Paste auth_token (40+ chars): ").strip()
        if len(auth_token) < 40:
            print(f"✗ auth_token too short ({len(auth_token)} chars, need 40+). Try again.")
            continue
        
        ct0 = input("Paste ct0 (160+ chars): ").strip()
        if len(ct0) < 160:
            print(f"✗ ct0 too short ({len(ct0)} chars, need 160+). Try again.")
            continue
        
        print("✓ Cookies validated successfully")
        return {"auth_token": auth_token, "ct0": ct0}


def main():
    """
    Main entry point. Parse arguments and extract cookies.
    """
    parser = argparse.ArgumentParser(
        description="Extract X (Twitter) authentication cookies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract manually and print to stdout
  python scripts/extract_x_auth.py --browser manual
  
  # Extract from Chrome and save to .env
  python scripts/extract_x_auth.py --browser chrome --output .env
  
  # Extract from Firefox and print to stdout
  python scripts/extract_x_auth.py --browser firefox
        """,
    )
    
    parser.add_argument(
        "--browser",
        choices=["chrome", "firefox", "manual"],
        default="manual",
        help="Browser to extract cookies from (default: manual)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: print to stdout)",
    )
    
    args = parser.parse_args()
    
    # Extract cookies based on browser choice
    if args.browser == "chrome":
        cookies = extract_from_chrome()
    elif args.browser == "firefox":
        cookies = extract_from_firefox()
    else:  # manual
        cookies = manual_input()
    
    # Check if extraction was successful
    if not cookies or "auth_token" not in cookies or "ct0" not in cookies:
        print("\n✗ Failed to extract cookies. Please try again.")
        sys.exit(1)
    
    # Format output
    output_lines = [
        f"X_AUTH_TOKEN={cookies['auth_token']}",
        f"X_CT0={cookies['ct0']}",
    ]
    output_text = "\n".join(output_lines)
    
    # Write to file or stdout
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(output_text + "\n")
        
        print(f"\n✓ Cookies saved to {output_path}")
        print(f"  Add these variables to your .env file or environment:")
        for line in output_lines:
            print(f"    {line}")
    else:
        print("\n✓ Extraction successful. Add these to your .env file:\n")
        print(output_text)
    
    print("\n✓ Done!")
    sys.exit(0)


if __name__ == "__main__":
    main()
