import os
import sys

import django


def main() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daybook_lite.settings')
    django.setup()
    print('Django setup OK')


if __name__ == '__main__':
    sys.exit(main())
