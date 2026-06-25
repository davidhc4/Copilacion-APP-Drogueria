[app]
# (str) Title of your application
title = Precios Droguerias

# (str) Package name
package.name = preciosfarmacenter

# (str) Package domain (needed for android/ios packaging)
package.domain = com.farmacenter

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,db,csv,ttf,json

# (str) Application versioning (method 1)
version = 3.9.9

# (list) Application requirements
requirements = python3,kivy==2.3.1,requests,certifi,fpdf2

# (str) Python version to use (android only)
android.python_version = 3.13

# (str) Icon of the application
icon.filename = %(source.dir)s/icono.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

#
# Android specific
#

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 28c

# (list) The Android archs to build for
android.archs = arm64-v8a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /usr/local/lib/android/sdk/ndk/28.0.13004108
