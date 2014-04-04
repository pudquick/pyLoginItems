# /System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Headers/LSSharedFileList.h

# Fun things:
# kLSSharedFileListFavoriteItems
# kLSSharedFileListFavoriteVolumes
# kLSSharedFileListRecentApplicationItems
# kLSSharedFileListRecentDocumentItems
# kLSSharedFileListRecentServerItems
# kLSSharedFileListSessionLoginItems
# kLSSharedFileListGlobalLoginItems - deprecated in 10.9

# Runs in user space, use this with a login script / launchd item / something running as the user

# Example usage:
#
# import pyLoginItems
# >>> pyLoginItems.list_login_items()
# [u'/Applications/Dropbox.app', u'/Applications/iTunes.app/Contents/MacOS/iTunesHelper.app']
#
# pyLoginItems.add_login_item('/Applications/Safari.app', 0)
# pyLoginItems.remove_login_item('/Applications/TextEdit.app')

from Foundation import NSURL
from LaunchServices import LSSharedFileListCreate, LSSharedFileListCopySnapshot, \
                    LSSharedFileListItemRemove, LSSharedFileListItemResolve, LSSharedFileListInsertItemURL, \
                    kLSSharedFileListSessionLoginItems, kLSSharedFileListNoUserInteraction, \
                    kLSSharedFileListItemBeforeFirst, kLSSharedFileListItemLast

def _get_login_items():
    # Setup the type of shared list reference we want
    list_ref = LSSharedFileListCreate(None, kLSSharedFileListSessionLoginItems, None)
    # Get the user's login items - actually returns two values, with the second being a seed value
    # indicating when the snapshot was taken (which is safe to ignore here)
    login_items,_ = LSSharedFileListCopySnapshot(list_ref, None)
    return [list_ref, login_items]

def _get_item_cfurl(an_item, flags=None):
    if flags is None:
        # Attempt to resolve the items without interacting or mounting
        flags = kLSSharedFileListNoUserInteraction + kLSSharedFileListNoUserInteraction
    err, a_CFURL, a_FSRef = LSSharedFileListItemResolve(an_item, flags, None, None)
    return a_CFURL

def list_login_items():
    # Attempt to find the URLs for the items without mounting drives
    URLs = []
    for an_item in _get_login_items()[1]:
        URLs.append(_get_item_cfurl(an_item).path())
    return URLs

def remove_login_item(path_to_item):
    current_paths = list_login_items()
    if path_to_item in current_paths:
        list_ref, current_items = _get_login_items()
        i = current_paths.index(path_to_item)
        target_item = current_items[i]
        result = LSSharedFileListItemRemove(list_ref, target_item)

def add_login_item(path_to_item, position=-1):
    # position:
    #   0..N: Attempt to insert at that index position, with 0 being first
    #     -1: Insert as last item
    # Note:
    # If the item is already present in the list, it will get moved to the new location automatically.
    list_ref, current_items = _get_login_items()
    added_item = NSURL.fileURLWithPath_(path_to_item)
    if position == 0:
        # Seems to be buggy, will force it below
        destination_point = kLSSharedFileListItemBeforeFirst
    elif position == -1:
        destination_point = kLSSharedFileListItemLast
    elif position >= len(current_items):
        # At or beyond to the end of the current list
        position = -1
        destination_point = kLSSharedFileListItemLast
    else:
        # 1 = after item 0, 2 = after item 1, etc.
        destination_point = current_items[position - 1]
    # The logic for LSSharedFileListInsertItemURL is generally fine when the item is not in the list
    # already (with the exception of kLSSharedFileListItemBeforeFirst which appears to be broken, period)
    # However, if the item is already in the list, the logic gets really really screwy.
    # Your index calculations are invalidated by OS X because you shift an item, possibly shifting the
    # indexes of other items in the list.
    # It's easier to just remove it first, then re-add it.
    current_paths = list_login_items()
    if (len(current_items) == 0) or (position == -1):
        # Either there's nothing there or it wants to be last
        # Just add the item, it'll be fine
        result = LSSharedFileListInsertItemURL(list_ref, destination_point, None, None, added_item, {}, [])
    elif (position == 0):
        # Special case - kLSSharedFileListItemBeforeFirst appears broken on (at least) 10.9
        # Remove if already in the list
        if path_to_item in current_paths:
            i = current_paths.index(path_to_item)
            old_item = current_items[i]
            result = LSSharedFileListItemRemove(list_ref, old_item)
            # Regenerate list_ref and items
            list_ref, current_items = _get_login_items()
        if (len(current_items) == 0):
            # Simple case if nothing remains in the list
            result = LSSharedFileListInsertItemURL(list_ref, destination_point, None, None, added_item, {}, [])
        else:
            # At least one item remains.
            # The fix for the bug is:
            # - Add our item after the first ('needs_fixing') item
            # - Move the 'needs_fixing' item to the end
            # - Move the 'needs_fixing' item after our added item (which is now first)
            needs_fixing = _get_item_cfurl(current_items[0])
            # Move our item
            result = LSSharedFileListInsertItemURL(list_ref, current_items[0], None, None, added_item, {}, [])
            if not (result is None):
                # Only shift if the first insert worked
                # Regenerate list_ref and items
                list_ref, current_items = _get_login_items()
                # Now move the old item last
                result = LSSharedFileListInsertItemURL(list_ref, kLSSharedFileListItemLast, None, None, needs_fixing, {}, [])
                # Regenerate list_ref and items
                list_ref, current_items = _get_login_items()
                # Now move the old item back under the new one
                result = LSSharedFileListInsertItemURL(list_ref, current_items[0], None, None, needs_fixing, {}, [])
    else:
        # We're aiming for an index based on something else in the list.
        # Only do something if we're not aiming at ourselves.
        insert_after_path = _get_item_cfurl(destination_point).path()
        if (insert_after_path != path_to_item):
            # Seems to be a different file
            if path_to_item in current_paths:
                # Remove our object if it's already present
                i = current_paths.index(path_to_item)
                self_item = current_items[i]
                result = LSSharedFileListItemRemove(list_ref, self_item)
                # Regenerate list_ref and items
                list_ref, current_items = _get_login_items()
                # Re-find our original target
                current_paths = list_login_items()
                i = current_paths.index(insert_after_path)
                destination_point = current_items[i]
            # Add ourselves after the file
            result = LSSharedFileListInsertItemURL(list_ref, destination_point, None, None, added_item, {}, [])
