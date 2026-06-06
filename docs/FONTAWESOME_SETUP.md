# Font Awesome Local Setup Instructions

## Download Font Awesome

1. Go to: https://fontawesome.com/download
2. Download "Font Awesome Free for the Web"
3. Extract the ZIP file

## Copy Files to Your Project

From the extracted folder, copy these directories to your Django static folder:

```
fontawesome-free-x.x.x-web/
├── css/
│   └── all.min.css (copy this)
├── webfonts/ (copy entire folder)
└── js/
    └── all.min.js (copy this)
```

To: `C:\Learnings\Python\daybook_lite\daybook_lite\static\`

Your structure should be:
```
static/
├── css/
│   └── all.min.css
├── webfonts/
│   ├── fa-solid-900.woff2
│   ├── fa-solid-900.ttf
│   └── (other font files)
└── js/
    └── all.min.js
```

## After Copying Files

The base.html will be automatically updated to use local Font Awesome files.
