from main import app, db

with app.app_context():
    print("🔄 Resetting database...")
    db.drop_all()
    db.create_all()
    print("✅ Database reset complete.")

    from main import get_valid_token

    print("🔄 Attempting Clio authorization...")
    try:
        token = get_valid_token()
        print("✅ Clio authorized. Access token:", token[:10], "...")
    except Exception as e:
        print("❌ Clio authorization failed:", str(e))