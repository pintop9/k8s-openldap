from ldap3 import Server, Connection, ALL, MODIFY_ADD
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError, LDAPException
import getpass
import sys
import pyotp
import qrcode

# --- Configuration ---
# To connect from your local machine, use a forwarded port.
# Run this in a separate terminal: kubectl port-forward -n ldap service/my-openldap 3890:389
LDAP_SERVER_URI = "localhost"
LDAP_PORT = 3890
BASE_DN = "dc=example,dc=org"
USERS_OU = "ou=users"

# Admin credentials are now needed for the script to modify the user's entry on first login
ADMIN_BIND_DN = "cn=admin,dc=example,dc=org"
ADMIN_PASSWORD = "Helmadmin123!" # Replace with your actual admin password if different

def generate_qr_for_user(username, secret_key, issuer_name="My-LDAP-App"):
    """Generates a TOTP provisioning URI and displays it as a QR code."""
    totp_uri = pyotp.totp.TOTP(secret_key).provisioning_uri(name=username, issuer_name=issuer_name)
    print("\n--- FIRST TIME MFA SETUP ---")
    print("Scan the QR Code below with your Google Authenticator app.")
    print("You will use the code from the app on your next login.\n")
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    qr.print_tty()

def enroll_user_for_mfa(username, user_dn):
    """Generates a secret, adds it to the user's LDAP entry, and shows a QR code."""
    try:
        # Connect as admin to modify the user's entry
        server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
        admin_conn = Connection(server, user=ADMIN_BIND_DN, password=ADMIN_PASSWORD, auto_bind=True)
        
        # Generate a new secret
        secret_key = pyotp.random_base32()
        
        # Modify the user to add the oathTOTPAccount object class and the secret
        admin_conn.modify(user_dn, {
            'objectClass': [(MODIFY_ADD, ['oathTOTPAccount'])],
            'oathTOTPSecret': [(MODIFY_ADD, [secret_key])]
        })
        
        if admin_conn.result['result'] == 0:
            print("\nSuccessfully enrolled user for MFA.")
            generate_qr_for_user(username, secret_key)
            admin_conn.unbind()
            return True
        else:
            print(f"Error enrolling user for MFA: {admin_conn.result['description']}")
            admin_conn.unbind()
            return False
            
    except Exception as e:
        print(f"An unexpected error occurred during MFA enrollment: {e}")
        return False

def authenticate_and_check_mfa(username, password):
    """
    Handles the entire login flow:
    1. Checks password.
    2. If password is good, checks if MFA is enrolled.
    3. If not enrolled, starts enrollment.
    4. If enrolled, asks for and verifies MFA code.
    """
    server = Server(LDAP_SERVER_URI, port=LDAP_PORT, get_info=ALL)
    user_dn = f"cn={username},{USERS_OU},{BASE_DN}"

    try:
        # Step 1: Authenticate user with their password
        print(f"\nStep 1: Authenticating password for {user_dn}...")
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        print("✅ Password authentication successful.")

        # Step 2: Check for existing MFA enrollment
        print("\nStep 2: Checking MFA enrollment status...")
        user_conn.search(user_dn, '(objectClass=oathTOTPAccount)', attributes=['oathTOTPSecret'])
        
        if not user_conn.entries or 'oathTOTPSecret' not in user_conn.entries[0]:
            # First-time login: Enroll the user
            print("MFA not configured for this user. Starting enrollment...")
            user_conn.unbind()
            return enroll_user_for_mfa(username, user_dn)
        else:
            # Subsequent login: Verify MFA code
            print("MFA is configured. Please provide your code.")
            secret_key = user_conn.entries[0]['oathTOTPSecret'].value
            mfa_code = input("Google Authenticator Code (will be visible): ")
            
            if not mfa_code.isdigit() or len(mfa_code) != 6:
                print("Invalid MFA code format. Must be 6 digits.")
                user_conn.unbind()
                return False

            totp = pyotp.TOTP(secret_key)
            if totp.verify(mfa_code):
                print("✅ MFA code verification successful.")
                user_conn.unbind()
                return True
            else:
                print("❌ MFA code verification failed.")
                user_conn.unbind()
                return False

    except LDAPBindError:
        print("❌ Password authentication failed (Invalid Credentials).")
        return False
    except LDAPSocketOpenError:
        print(f"Connection failed: Could not connect to LDAP server at {LDAP_SERVER_URI}:{LDAP_PORT}.")
        print("Please ensure kubectl port-forward is running.")
        return False
    except LDAPException as e:
        print(f"An LDAP error occurred: {e}")
        return False

if __name__ == "__main__":
    print("--- Advanced LDAP CLI Authenticator ---")
    username = input("Username (e.g., asmith): ")
    if not username:
        sys.exit("Username cannot be empty.")
        
    password = getpass.getpass("Password: ")
    if not password:
        sys.exit("Password cannot be empty.")

    if authenticate_and_check_mfa(username, password):
        print("\nAuthentication process complete.")
    else:
        print("\nAuthentication process failed.")
