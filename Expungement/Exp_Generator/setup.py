from setuptools import setup

APP = ['expungement2.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': ['tkinter', 'docx', 'python-docx'],  # Explicitly include both docx and python-docx
    'includes': ['docx', 'python-docx'],
    'plist': {
        'CFBundleName': 'Expungement Petition Generator',
        'CFBundleDisplayName': 'Expungement Petition Generator',
        'CFBundleIdentifier': 'com.yourdomain.expungement',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
