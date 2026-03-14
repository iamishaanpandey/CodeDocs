import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tst
from tree_sitter import Language

try:
    js_lang_ptr = tsjs.language()
    print(f"JS Lang Ptr Type: {type(js_lang_ptr)}")
    print(f"JS Lang Ptr Value: {js_lang_ptr}")
    
    # Try to initialize
    try:
        lang = Language(js_lang_ptr, "javascript")
        print("Successfully initialized with (ptr, name)")
    except Exception as e:
        print(f"Failed with (ptr, name): {e}")
        
    try:
        lang = Language(js_lang_ptr)
        print("Successfully initialized with (ptr)")
    except Exception as e:
        print(f"Failed with (ptr): {e}")

except Exception as e:
    print(f"Main error: {e}")
