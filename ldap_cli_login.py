import ldap3
from ldap3 import Server, Connection, ALL, MODIFY_ADD
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError, LDAPException
import sys
import pyotp
import qrcode
import platform
import os

# Platform-specific input for masking password with asterisks
if platform.system() == "Windows":
    import msvcrt
else:
    import termios
    import tty

# --- Configuration ---
LDAP_SERVER_URI = "localhost"
LDAP_PORT = 3890
BASE_DN = "dc=example,dc=org"
USERS_OU = "ou=users"
ADMIN_BIND_DN = "cn=admin,dc=example,dc=org"
ADMIN_PASSWORD = "Helmadmin123!"

def verify_mfa_code(secret_key, mfa_code):
    """
    Verifies the provided 6-digit MFA code against the user's secret key.
    """
    if not secret_key:
        print("MFA check failed: Secret key is missing.")
        return False
    totp = pyotp.TOTP(secret_key)
    is_valid = totp.verify(mfa_code)
    print(f"MFA code verification: {'Successful' if is_valid else 'Failed'}")
    return is_valid

def _getpass_with_asterisks(prompt="Password: "):
    """
    Reads password input from the console, displaying asterisks for each character.
    Handles backspace. Not as robust as getpass() for all edge cases/terminals.
    """
    print(prompt, end='', flush=True)
    password = []
    while True:
        if platform.system() == "Windows":
            char = msvcrt.getch()
            if char == b'\r' or char == b'\n':
                break
            if char == b'\x08': # Backspace
                if password:
                    password.pop()
                    sys.stdout.write('\b \b') # Erase asterisk
                    sys.stdout.flush()
            else:
                password.append(char.decode('utf-8'))
                sys.stdout.write('*')
                sys.stdout.flush()
        else: # Unix/Linux/macOS
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                char = sys.stdin.read(1)
                if char == '\r' or char == '\n':
                    break
                if ord(char) == 127: # Backspace
                    if password:
                        password.pop()
                        sys.stdout.write('\b \b')
                        sys.stdout.flush()
                else:
                    password.append(char)
                    sys.stdout.write('*')
                    sys.stdout.flush()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print() # Newline after password
    return "".join(password)


def generate_qr_for_user(username, secret_key, issuer_name="My-LDAP-App"):
    """Generates a smaller TOTP QR code and handles user confirmation/cancellation."""
    totp_uri = pyotp.totp.TOTP(secret_key).provisioning_uri(name=username, issuer_name=issuer_name)
    
    print("\n--- FIRST TIME OTP APP SETUP ---")
    print(f"Scan this QR code with your OTP app (e.g., Google Authenticator, Authy) for user '{username}'.")
    print("This will add 'My-LDAP-App' to your OTP app and start generating 6-digit codes.\n")
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=2, border=2) # Smaller QR
    qr.add_data(totp_uri)
    qr.make(fit=True)
    qr.print_tty()
    
    print("\nQR code displayed.")
    while True:
        choice = input("Press 'y' to confirm you have scanned the code and proceed, or 'n' to cancel OTP enrollment for now: ").lower()
        if choice == 'y':
            return True
        elif choice == 'n':
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'.")


def enroll_user_for_mfa(username, user_dn):
    """
    Generates a secret, attempts to add it to the user's LDAP entry,
    and shows a QR code. Returns True if enrollment confirmed, False if cancelled/failed.
    """
    try:
        server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
        admin_conn = Connection(server, user=ADMIN_BIND_DN, password=ADMIN_PASSWORD, auto_bind=True)
        secret_key = pyotp.random_base32()
        
        # Ask user to scan QR code first
        if not generate_qr_for_user(username, secret_key):
            admin_conn.unbind()
            print("OTP enrollment cancelled by user.")
            return False # User cancelled enrollment

        # If user confirmed scanning, then save to LDAP
        admin_conn.modify(user_dn, {
            'objectClass': [(MODIFY_ADD, ['oathTOTPAccount'])],
            'oathTOTPSecret': [(MODIFY_ADD, [secret_key])]
        })
        
        if admin_conn.result['result'] == 0:
            print("✅ Successfully saved OTP secret to your LDAP profile.")
            admin_conn.unbind()
            return True
        else:
            print(f"❌ Error saving OTP secret to LDAP: {admin_conn.result['description']}")
            admin_conn.unbind()
            return False
            
    except Exception as e:
        print(f"An unexpected error occurred during OTP enrollment: {e}")
        return False

def check_password_and_get_connection(username, password):
    """Authenticates a user's password only. Returns the connection on success."""
    server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
    user_dn = f"cn={username},{USERS_OU},{BASE_DN}"
    try:
        print(f"Step 1: Authenticating password for {user_dn}...")
        conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        print("✅ Password authentication successful.")
        return conn
    except LDAPBindError:
        print("❌ Password authentication failed (Invalid Credentials).")
        return None
    except LDAPSocketOpenError:
        print(f"Connection failed: Could not connect to LDAP server at {LDAP_SERVER_URI}:{LDAP_PORT}.")
        print("Please ensure kubectl port-forward is running.")
        return None
    except LDAPException as e:
        print(f"An LDAP error occurred: {e}")
        return None


if __name__ == "__main__":
    print("--- Advanced LDAP CLI Authenticator ---")
    username = input("Username (e.g., asmith): ")
    if not username:
        sys.exit("Username cannot be empty.")

    user_conn = None
    max_password_attempts = 3
    for attempt in range(max_password_attempts):
        password = _getpass_with_asterisks(f"Password (attempt {attempt + 1}/{max_password_attempts}): ")
        if not password:
            print("Password cannot be empty.")
            continue
        
        user_conn = check_password_and_get_connection(username, password)
        if user_conn: # Password authenticated
            break 
    
    if not user_conn:
        print("\nToo many failed password attempts. Exiting.")
        sys.exit(1)

    # Password is correct, now check MFA
    user_dn = f"cn={username},{USERS_OU},{BASE_DN}"
    
    # Retrieve MFA secret to determine enrollment status
    try:
        # Re-bind as admin to get the user's secret for verification/enrollment decision
        server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
        admin_conn_for_secret = Connection(server, user=ADMIN_BIND_DN, password=ADMIN_PASSWORD, auto_bind=True)
        admin_conn_for_secret.search(user_dn, '(objectClass=oathTOTPAccount)', attributes=['oathTOTPSecret'])
        
        has_mfa_secret = False
        mfa_secret_value = None
        if admin_conn_for_secret.entries and 'oathTOTPSecret' in admin_conn_for_secret.entries[0]:
            has_mfa_secret = True
            mfa_secret_value = admin_conn_for_secret.entries[0]['oathTOTPSecret'].value
        admin_conn_for_secret.unbind() # Close admin connection
        
    except LDAPException as e:
        print(f"Error checking MFA enrollment status: {e}")
        sys.exit(1)

    if not has_mfa_secret:
        # First-time login: Offer MFA enrollment
        print("\nMFA not configured for this user. Offering enrollment...")
        if enroll_user_for_mfa(username, user_dn):
            # If enrollment was successful (user scanned QR and confirmed), proceed to MFA verification
            # The secret value is now stored and needs to be retrieved for verification
            # Re-fetch the secret after enrollment
            try:
                server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
                admin_conn_re_fetch_secret = Connection(server, user=ADMIN_BIND_DN, password=ADMIN_PASSWORD, auto_bind=True)
                admin_conn_re_fetch_secret.search(user_dn, '(objectClass=oathTOTPAccount)', attributes=['oathTOTPSecret'])
                if admin_conn_re_fetch_secret.entries and 'oathTOTPSecret' in admin_conn_re_fetch_secret.entries[0]:
                    mfa_secret_value = admin_conn_re_fetch_secret.entries[0]['oathTOTPSecret'].value
                    has_mfa_secret = True
                admin_conn_re_fetch_secret.unbind()
            except LDAPException as e:
                print(f"Error re-fetching MFA secret after enrollment: {e}")
                sys.exit(1)
        else:
            # User cancelled enrollment, proceed as password-only success for this session
            print("OTP enrollment skipped. Logging in with password only for this session.")
            print("\n✅ Authentication (Password Only) successful!")
            sys.exit(0)
    
    # If MFA is configured (or just enrolled), proceed to verify OTP
    if has_mfa_secret:
        print("\nMFA is configured. Please provide your OTP code.")
        max_mfa_attempts = 3
        for attempt in range(max_mfa_attempts):
            mfa_code = input(f"OTP Code (will be visible, attempt {attempt + 1}/{max_mfa_attempts}): ")
            
            if not mfa_code.isdigit() or len(mfa_code) != 6:
                print("Invalid OTP code format. Must be 6 digits.")
                continue

            if verify_mfa_code(mfa_secret_value, mfa_code):
                print("\n✅ Full authentication (Password + OTP) successful!")
                sys.exit(0)
            else:
                print("❌ OTP code verification failed.")
        
        print("\nToo many failed OTP attempts. Exiting.")
        sys.exit(1)
    else: # Should not be reached if has_mfa_secret is handled above
        print("\nUnexpected authentication state. Exiting.")
        sys.exit(1)