/* Xrero Office for macOS - first-run launcher (CFBundleExecutable).
 *
 * Seeds first-run preferences, then execv()s the real app binary next to it. execv keeps the PID, so
 * LaunchServices, the Dock and Apple Events (Finder "open document") see one ordinary app process.
 *
 * Why: the bundled Sparkle 2.0.0 is driven by its SUUpdater compatibility shim, which asks
 * "Check for updates automatically?" on the very FIRST launch unless the user defaults (not Info.plist)
 * already hold an answer. Xrero announces Mac releases on xrero.com; Xrero Office > Check for Updates...
 * keeps working against Xrero's own appcast.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define APP_ID   CFSTR("com.xrero.office")
#define REAL_EXE "XreroOffice"

static void seed(CFStringRef key, CFPropertyListRef value)
{
    CFPropertyListRef cur = CFPreferencesCopyAppValue(key, APP_ID);
    if (cur) { CFRelease(cur); return; }   /* the user's own answer wins */
    CFPreferencesSetAppValue(key, value, APP_ID);
}

int main(int argc, char *argv[])
{
    (void)argc;
    seed(CFSTR("SUEnableAutomaticChecks"), kCFBooleanFalse);
    CFPreferencesAppSynchronize(APP_ID);

    char self[PATH_MAX], real[PATH_MAX + 32];
    uint32_t n = sizeof self;
    if (_NSGetExecutablePath(self, &n) != 0) return 111;
    char *slash = strrchr(self, '/');
    if (!slash) return 112;
    *slash = 0;
    snprintf(real, sizeof real, "%s/%s", self, REAL_EXE);
    argv[0] = real;
    execv(real, argv);
    perror("Xrero Office: cannot start " REAL_EXE);
    return 113;
}
