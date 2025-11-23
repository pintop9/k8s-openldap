from ldap3 import Server, Connection, ALL, MODIFY_ADD
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError, LDAPException
import getpass
import sys
import pyotp
import qrcode

# --- Configuration ---
LDAP_SERVER_URI = "localhost"
LDAP_PORT = 3890
BASE_DN = "dc=example,dc=org"
USERS_OU = "ou=users"
ADMIN_BIND_DN = "cn=admin,dc=example,dc=org"
ADMIN_PASSWORD = "Helmadmin123!"

def generate_qr_for_user(username, secret_key, issuer_name="My-LDAP-App"):
    """Generates a smaller TOTP QR code and waits for user confirmation."""
    totp_uri = pyotp.totp.TOTP(secret_key).provisioning_uri(name=username, issuer_name=issuer_name)
    print("\n--- FIRST TIME MFA SETUP ---")
    print("Scan the QR Code below with your OTP app (e.g., Google Authenticator, Authy).\n")
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    qr.print_tty()
    
    print("\nQR code displayed.")
    while True:
        proceed = input("Once you have scanned the code, press 'y' to continue: ").lower()
        if proceed == 'y':
            break

def enroll_user_for_mfa(username, user_dn):
    """Generates a secret, adds it to the user's LDAP entry, and shows a QR code."""
    try:
        server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
        admin_conn = Connection(server, user=ADMIN_BIND_DN, password=ADMIN_PASSWORD, auto_bind=True)
        secret_key = pyotp.random_base32()
        
        admin_conn.modify(user_dn, {
            'objectClass': [(MODIFY_ADD, ['oathTOTPAccount'])],
            'oathTOTPSecret': [(MODIFY_ADD, [secret_key])]
        })
        
        if admin_conn.result['result'] == 0:
            print("✅ Successfully enrolled user for MFA.")
            generate_qr_for_user(username, secret_key)
            admin_conn.unbind()
            return True
        else:
            print(f"❌ Error enrolling user for MFA: {admin_conn.result['description']}")
            admin_conn.unbind()
            return False
            
    except Exception as e:
        print(f"An unexpected error occurred during MFA enrollment: {e}")
        return False

def check_password(username, password):
    """Authenticates a user's password only. Returns the connection on success."""
    server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
    user_dn = f"cn={username},{USERS_OU},{BASE_DN}"
    try:
        print(f"\nStep 1: Authenticating password for {user_dn}...")
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

    # --- Password Authentication Loop ---
    user_conn = None
    max_password_attempts = 3
    for attempt in range(max_password_attempts):
        password = getpass.getpass(f"Password (attempt {attempt + 1}/{max_password_attempts}): ")
        if not password:
            print("Password cannot be empty.")
            continue
        
        user_conn = check_password(username, password)
        if user_conn:
            break # Exit loop on successful password auth
    
    if not user_conn:
        print("\nToo many failed password attempts. Exiting.")
        sys.exit(1)

    # --- MFA Check / Enrollment ---
    print("\nStep 2: Checking MFA enrollment status...")
    user_dn = f"cn={username},{USERS_OU},{BASE_DN}"
    user_conn.search(user_dn, '(objectClass=oathTOTPAccount)', attributes=['oathTOTPSecret'])
    
    if not user_conn.entries or 'oathTOTPSecret' not in user_conn.entries[0]:
        # First-time login: Enroll the user
        print("MFA not configured for this user. Starting enrollment...")
        user_conn.unbind() # Close the connection before starting enrollment
        if not enroll_user_for_mfa(username, user_dn):
             sys.exit("MFA enrollment failed. Please contact an administrator.")
        print("\nEnrollment complete. Please log in again using your new OTP code on your next login.")
        sys.exit(0)
    else:
        # Subsequent login: Verify MFA code
        print("MFA is configured. Please provide your OTP code.")
        secret_key = user_conn.entries[0]['oathTOTPSecret'].value
        user_conn.unbind() # Close the connection before starting the OTP loop
        
        max_mfa_attempts = 3
        for attempt in range(max_mfa_attempts):
            mfa_code = input(f"OTP Code (will be visible, attempt {attempt + 1}/{max_mfa_attempts}): ")
            
            if not mfa_code.isdigit() or len(mfa_code) != 6:
                print("Invalid OTP code format. Must be 6 digits.")
                continue

            totp = pyotp.TOTP(secret_key)
            if totp.verify(mfa_code):
                print("\n✅ Full authentication (Password + OTP) successful!")
                sys.exit(0) # Success!
            else:
                print("❌ OTP code verification failed.")
        
        print("\nToo many failed OTP attempts. Exiting.")
        sys.exit(1)