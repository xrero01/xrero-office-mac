// XreroUI.framework - Mac App Store build only.
//
// The official ONLYOFFICE bundle links Sparkle (a self-updater) and its MainMenu nib instantiates the class
// "SUUpdater" by name for "Check for Updates...". The App Store forbids self-updating code (guideline 2.4.5),
// so the Mac App Store build ships WITHOUT Sparkle: the main binary's Sparkle load command is pointed at this
// small framework instead (same-length path), which provides an inert SUUpdater. It never downloads or installs
// anything; it only removes the "Check for Updates..." menu item, because the App Store delivers updates.
#import <AppKit/AppKit.h>

@interface SUUpdater : NSObject
+ (instancetype)sharedUpdater;
- (IBAction)checkForUpdates:(id)sender;
- (BOOL)validateMenuItem:(NSMenuItem *)item;
@property (nonatomic) BOOL automaticallyChecksForUpdates;
@property (nonatomic) BOOL automaticallyDownloadsUpdates;
@property (nonatomic, copy) NSURL *feedURL;
@property (nonatomic) NSTimeInterval updateCheckInterval;
@property (nonatomic, weak) id delegate;
@end

static void XRRemoveUpdateItems(NSMenu *menu)
{
    for (NSMenuItem *item in [menu.itemArray copy]) {
        if (item.action == @selector(checkForUpdates:)) {
            NSInteger i = [menu indexOfItem:item];
            [menu removeItem:item];
            // a separator left directly above the removed item, with nothing after it, goes too
            if (i > 0 && i - 1 < menu.numberOfItems && [menu itemAtIndex:i - 1].isSeparatorItem &&
                (i >= menu.numberOfItems || [menu itemAtIndex:i].isSeparatorItem))
                [menu removeItemAtIndex:i - 1];
            continue;
        }
        if (item.submenu) XRRemoveUpdateItems(item.submenu);
    }
}

@implementation SUUpdater
+ (instancetype)sharedUpdater
{
    static SUUpdater *u;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ u = [[SUUpdater alloc] init]; });
    return u;
}
+ (instancetype)updaterForBundle:(NSBundle *)bundle { (void)bundle; return [self sharedUpdater]; }
- (void)awakeFromNib
{
    // the main menu is installed after the nib finishes loading: tidy it on the next turns of the run loop
    for (int n = 1; n <= 3; n++)
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(n * 0.5 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            if (NSApp.mainMenu) XRRemoveUpdateItems(NSApp.mainMenu);
        });
}
- (IBAction)checkForUpdates:(id)sender { (void)sender; }
- (void)checkForUpdatesInBackground {}
- (void)checkForUpdateInformation {}
- (void)resetUpdateCycle {}
- (BOOL)validateMenuItem:(NSMenuItem *)item { (void)item; return NO; }
- (id)valueForUndefinedKey:(NSString *)key { (void)key; return nil; }
- (void)setValue:(id)value forUndefinedKey:(NSString *)key { (void)value; (void)key; }
@end
