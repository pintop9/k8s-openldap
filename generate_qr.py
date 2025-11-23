import pyotp
import qrcode
import sys

def generate_qr_for_user(username, secret_key, issuer_name="My-LDAP-App"):
    """
    Generates a TOTP provisioning URI and displays it as a QR code
    in the terminal.
    """
    if not secret_key:
        print("Error: Secret key cannot be empty.", file=sys.stderr)
        sys.exit(1)

    # Create the provisioning URI that Google Authenticator understands
    # format: otpauth://totp/Issuer:Account?secret=SECRET&issuer=Issuer
    totp_uri = pyotp.totp.TOTP(secret_key).provisioning_uri(
        name=username,
        issuer_name=issuer_name
    )

    print("\n--- TOTP Provisioning URI ---")
    print(totp_uri)
    print("\n--- Scan the QR Code below with your Google Authenticator app ---")

    # Generate and print the QR code to the terminal
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(totp_uri)
    qr.make(fit=True)
    
    # Print the QR code to the terminal as ASCII art
    qr.print_tty()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_qr.py <username> <secret_key>", file=sys.stderr)
        print("Example: python generate_qr.py asmith JBSWY3DPEHPK3PXP", file=sys.stderr)
        sys.exit(1)

    user_arg = sys.argv[1]
    secret_arg = sys.argv[2]
    
    generate_qr_for_user(user_arg, secret_arg)
