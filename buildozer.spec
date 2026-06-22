[app]

# (str) Title of your application
title = Precios Farmacenter

# (str) Package name
package.name = preciosfarmacenter

# (str) Package domain (needed for android/ios packaging)
package.domain = com.farmacenter

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,db,csv

# (str) Application versioning (method 1)
version = 2.9.9

# (list) Application requirements
# IMPORTANTE: cython aquí permite compilar licencia.py a binario (.so)
# y no dejarlo como .pyc fácilmente descompilable.
requirements = python3,kivy==2.3.1,requests,certifi,cython

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/logo_farmacenter.png

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
android.permissions = INTERNET, ACCESS_NETWORK_STATE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (str) Android NDK version to use
#android.ndk = 25b

# (list) The Android archs to build for
android.archs = arm64-v8a

android.ndk = 28c

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

#
# Python for android (p4a) specific
#

# (str) The format used to package the app for debug mode (apk or aar).
# p4a.bootstrap = sdl2

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

android.sdk_path = /usr/local/lib/android/sdk

android.ndk_path = /usr/local/lib/android/ndk
