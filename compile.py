import re, uuid, os.path, json, plistlib
import sublime, sublime_plugin
from . import templates
from .color import *

PATH_SEPARATOR = "\\" if sublime.platform() == "windows" else "/"

def plugin_loaded():
    global PACKAGES_PATH, SYNESTHESIA_INCLUDE_PATH, SYNESTHESIA_INCLUDE_PATH_RELATIVE, SYNESTHESIA_OUTPUT_PATH, SYNESTHESIA_OUTPUT_PATH_RELATIVE
    PACKAGES_PATH = sublime.packages_path()
    __SYNESTHESIA_INCLUDE_PATH = "User/Synesthesia/include/"
    __SYNESTHESIA_SYNTAXES_PATH = "Synesthesia-Syntaxes"
    SYNESTHESIA_INCLUDE_PATH = os.path.join(sublime.packages_path(), __SYNESTHESIA_INCLUDE_PATH)
    SYNESTHESIA_INCLUDE_PATH_RELATIVE = "Packages/" + __SYNESTHESIA_INCLUDE_PATH
    SYNESTHESIA_OUTPUT_PATH = os.path.join(sublime.packages_path(), __SYNESTHESIA_SYNTAXES_PATH)
    SYNESTHESIA_OUTPUT_PATH_RELATIVE = "Packages/" + __SYNESTHESIA_SYNTAXES_PATH

def write_file(filepath, s):
    f = open(filepath, 'w')
    f.write(s)
    f.close()

def read_file(filepath):
    f = open(filepath, 'r')
    result = f.read()
    f.close()
    return result

def strip_non_alpha(string):
    return re.sub("[^A-Za-z]+", "", string)

def split_filepath(abspath):
    segments = abspath.split(PATH_SEPARATOR)
    filename = segments[-1:][0]
    extparts = filename.split(".")
    return PATH_SEPARATOR.join(segments[:-1]), extparts[0], '.'.join(extparts[1:])

def ensure_directory_exists(path):
    if not os.path.exists(path):
        print("%s does not exist; created" % path)
        os.makedirs(path)

def read_default_settings(view):
    if sublime.platform() == "windows":
        # Prevent regex error: [re.error: invalid group reference x] if there's [\x] characters in the path
        color_scheme_path = re.sub("^Packages", sublime.packages_path().replace('\\', '/'), view.settings().get('color_scheme'))
    else:
        color_scheme_path = re.sub("^Packages", sublime.packages_path(), view.settings().get('color_scheme'))

    if (os.path.exists(color_scheme_path)):
        settings_block = re.compile(r"[ \t]+<dict>\s+<key>settings</key>[\s\w></#]+</dict>")
        settings_text = read_file(color_scheme_path)
        match = settings_block.search(settings_text)
        if match:
            default_colors = match.group(0)
            return default_colors

    return None

def load_json_data(source, path=True):
    _, themename, ext = split_filepath(source)

    entries = None
    try:
        if path:
            entries = json.loads(read_file(source))
        else:
            entries = json.loads(source)
    except ValueError:
        sublime.status_message("%s.%s is not a valid JSON file." % (themename, ext))
    except IOError:
        print("%s.%s could not be loaded." % (themename, ext))

    return themename, entries

def get_include_contents():
    ''' Returns the contents of the include directory, abstracting away differences between directory and .sublime_package format '''
    include = re.compile(SYNESTHESIA_INCLUDE_PATH_RELATIVE)
    # Get json file names in include directory
    files = [include.sub('', x) for x in sublime.find_resources('*.json') if include.search(x) is not None]
    # Strip extension
    return [x[:-5] for x in files]

def color(key, c, dark=False):
    c = c.lower()
    if dark and c == "auto":
        c = string_to_dark_color(key)
    elif c == "random":
        c = random_color()
    elif c == "auto":
        c = string_to_color(key)
    # elif c in name_to_hex:
    #     c = name_to_hex[c]
    return c

def first_valid_path(*paths):
    ''' Takes a list of paths, returning the first valid path, or None if none are valid '''
    for path in paths:
        if os.path.isfile(path):
            return path
    return None

class SynesthesiaCompileCommand(sublime_plugin.WindowCommand):
    def run(self, cmd = []):

        path = cmd[0] if len(cmd) > 0 else self.window.active_view().file_name()
        filepath = os.path.abspath(path)
        themename, entries = load_json_data(filepath)
        directory, _, _ = split_filepath(filepath)

        if not entries:
            return

        hs = HighlightingScheme(directory, entries)

        default_colors = read_default_settings(self.window.active_view())
        if default_colors:
            hs.default_colors = default_colors

        hs.save(themename)

class Keyword():
    count = 0

    def __init__(self, regex, value):

        self.color = None
        self.background_color = None
        self.fontstyle = []
        self.whole_word = False # do i really need this after modifying the regex?
        self.case_insensitive = False # same for this one
        self.name = strip_non_alpha(regex)
        self.regex = regex

        if type(value) == str:
            self.color = color(regex, value)
        elif type(value) == dict:
            if "color" in value:
                self.color = color(regex, value["color"])
            if "background" in value:
                self.background_color = color(key, value["background"], True)
            if "italic" in value and value["italic"]:
                self.fontstyle.append("italic")
            if "bold" in value and value["bold"]:
                self.fontstyle.append("bold")
            if "whole-word" in value and value["whole-word"]:
                self.whole_word = True
            if "case-insensitive" in value and value["case-insensitive"]:
                self.case_insensitive = True

        # Post-processing of regex

        if self.whole_word or self.name == regex:
            # regex is completely alphabetical;
            # automatically enforce word boundary
            self.regex = "\\b%s\\b" % regex
        if self.case_insensitive:
            self.regex = "(?i:%s)" % regex
        self.name = "%s_%d" % (self.name, Keyword.count)
        Keyword.count += 1

def process_tmLanguage(scheme_name, path, keywords, insertion_scope):
    plist = plistlib.readPlist(path)

    plist['name'] = scheme_name
    plist['scopeName'] += '.' + scheme_name

    # Locate the scope to make insertions in
    insertion_point = plist
    for scope in insertion_scope.split(r'.'):
        if scope not in insertion_point:
            print("Could not find scope %s from specified insertion scope %s!" % (scope, insertion_scope))
            print("tmLanguage not generated")
            return
        insertion_point = insertion_point[scope]
    if "patterns" not in insertion_point:
        print("Could not find key 'patterns' in specified insertion scope %s!" % (insertion_scope))
        print("tmLanguage not generated")
        return
    else:
        insertion_point = insertion_point["patterns"]

    # TODO other features, font, etc.
    for keyword in keywords:
        plist['repository'][keyword.name] = {
            'match': keyword.regex,
            'name': 'meta.other.%s.%s' % (scheme_name, keyword.name)
        }
        insertion_point.append({
            'include': '#%s' % (keyword.name)
        })

    path = os.path.join(SYNESTHESIA_OUTPUT_PATH, scheme_name + '.tmLanguage')

    plistlib.writePlist(plist, path)
    print("Generated %s" % (path))

def process_tmTheme(scheme_name, path, keywords):
    plist = plistlib.readPlist(path)

    plist['name'] = scheme_name

    # TODO other features
    for keyword in keywords:
        plist['settings'].append({
            'name': keyword.name,
            'scope': 'meta.other.%s.%s' % (scheme_name, keyword.name),
            'settings': {'foreground': keyword.color}
        })

    path = os.path.join(SYNESTHESIA_OUTPUT_PATH, scheme_name + '.tmTheme')

    plistlib.writePlist(plist, path)
    print("Generated %s" % (path))

def process_sublime_settings(scheme_name, path, existing_settings):
    settings = json.loads(read_file(path))

    for key in existing_settings:
        settings[key] = existing_settings[key]
    settings["color_scheme"] = '%s/%s.tmTheme' % (SYNESTHESIA_OUTPUT_PATH_RELATIVE, scheme_name)

    path = os.path.join(SYNESTHESIA_OUTPUT_PATH, scheme_name + '.sublime-settings')

    write_file(path, json.dumps(settings, sort_keys=False, indent=4, separators=(',', ': ')))
    print("Generated %s" % (path))

class HighlightingScheme():
    """
    A highlighting scheme consists of:

    - a syntax definition
    - a color theme
    - a settings file

    """

    default_colors = templates.default_colors

    def __init__(self, directory, data):
        self.directory = directory
        self.data = data

    def save(self, theme_name):
        # initialization
        autocompletion = "autocompletion" in self.data and self.data["autocompletion"]
        keywords = []
        theme_scopes = []
        keyword_map = "keywords" in self.data and self.data["keywords"] or {}
        settings_map = "settings" in self.data and self.data["settings"] or {}
        count = 0
        auto_keywords_list = "auto_keywords" in self.data and self.data["auto_keywords"] or []
        random_keywords_list = "random_keywords" in self.data and self.data["random_keywords"] or []
        cyclic_keywords_list = "cyclic_keywords" in self.data and self.data["cyclic_keywords"] or []
        cyclic_seed = "cyclic_seed" in self.data and self.data["cyclic_seed"] or None

        extensions = "extensions" in self.data and self.data["extensions"] or ["txt", "md"]

        # resolve dependencies (depth-first)
        if "include" in self.data:
            inclusions = self.data["include"]
            inclusions.reverse()
            already_included = [theme_name]
            in_include_directory = get_include_contents()
            while len(inclusions) > 0:
                i = inclusions.pop()
                # prevents recursive dependency, since it only looks in the same directory
                if i in already_included:
                    print("%s is already included." % (i))
                else:
                    already_included.append(i)
                    print("Looking for %s in %s..." % (i, self.directory), end=' ')
                    _, entries = load_json_data(os.path.join(self.directory, i + '.json'))
                    if entries is not None:
                        print("Found!")
                    else:
                        print("Looking in %s..." % (SYNESTHESIA_INCLUDE_PATH_RELATIVE), end=' ')
                        if i in in_include_directory:
                            print("Found!")
                            _, entries = load_json_data(sublime.load_resource(os.path.join(SYNESTHESIA_INCLUDE_PATH_RELATIVE, i + '.json')), False)
                        else:
                            print("Could not find %s." % (i))

                    # Proceed if after all that we actually ended up with some input
                    if entries is not None:
                        print("%s included." % (i + '.json'))
                        if "include" in entries:
                            to_include = entries["include"]
                            to_include.reverse()
                            inclusions.extend(to_include)
                        if "keywords" in entries:
                            new_keywords = entries["keywords"]
                            for key in list(new_keywords.keys()):
                                # won't add colliding names
                                if key not in keyword_map:
                                    keyword_map[key] = new_keywords[key]

        # turn syntactic sugar into actual keywords
        for keyword in auto_keywords_list:
            if keyword not in keyword_map:
                keyword_map[keyword] = "auto"

        for keyword in random_keywords_list:
            if keyword not in keyword_map:
                keyword_map[keyword] = "random"

        cyclic = cyclic_colors(len(cyclic_keywords_list), cyclic_seed)
        if not cyclic_seed:
            print("Cyclic colors:", cyclic)
        for keyword, color in zip(cyclic_keywords_list, cyclic):
            if keyword not in keyword_map:
                keyword_map[keyword] = color

        # generate syntax and theme files
        if "deriving" in self.data:
            self.generate_derived_files(theme_name, keyword_map, settings_map)
        else:
            self.generate_non_derived_files(autocompletion, theme_name, settings_map, extensions, theme_scopes, keywords, keyword_map, count)

        sublime.status_message("Highlighting scheme %s generated." % theme_name)

    def generate_derived_files(self, theme_name, keyword_map, settings_map):
        # Check inputs are present
        for required_key in ["tmLanguage", "tmTheme", "sublime-settings", "tmLanguage_scope"]:
            if required_key not in self.data["deriving"]:
                print("Missing %s key in 'deriving' field!" % (required_key))
                return

        # Format file names correctly
        for file_name_key in ["tmLanguage", "tmTheme", "sublime-settings"]:
            self.data["deriving"][file_name_key] += "." + file_name_key

        tmTheme = self.data["deriving"]["tmTheme"]
        tmLanguage = self.data["deriving"]["tmLanguage"]
        sublime_settings = self.data["deriving"]["sublime-settings"]

        derived_theme_path = first_valid_path(os.path.join(self.directory, tmTheme), os.path.join(SYNESTHESIA_OUTPUT_PATH, tmTheme))
        derived_language_path = first_valid_path(os.path.join(self.directory, tmLanguage), os.path.join(SYNESTHESIA_OUTPUT_PATH, tmLanguage))
        derived_settings_path = first_valid_path(os.path.join(self.directory, sublime_settings), os.path.join(SYNESTHESIA_OUTPUT_PATH, sublime_settings))

        if not derived_theme_path:
            print("Could not locate %s" % tmTheme)
            return
        if not derived_language_path:
            print("Could not locate %s" % tmLanguage)
            return
        if not derived_settings_path:
            print("Could not locate %s" % sublime_settings)
            return

        # All required info is present
        # Build data structures
        keywords = [Keyword(regex, value) for (regex, value) in keyword_map.items()]

        ensure_directory_exists(SYNESTHESIA_OUTPUT_PATH)

        process_tmLanguage(theme_name, derived_language_path, keywords, self.data["deriving"]["tmLanguage_scope"])
        process_tmTheme(theme_name, derived_theme_path, keywords)
        process_sublime_settings(theme_name, derived_settings_path, settings_map)

    def generate_non_derived_files(self, autocompletion, theme_name, settings_map, extensions, theme_scopes, keywords, keyword_map, count):
        for key in list(keyword_map.keys()):
            regex = key
            value = keyword_map[key]

            options = []
            case_insensitive = False
            whole_word = False

            if type(value) == str:
                options.append(templates.theme_element_foreground % color(key, value))
            elif type(value) == dict:
                fontstyle = []
                if "color" in value:
                    options.append(templates.theme_element_foreground % color(key, value["color"]))
                if "background" in value:
                    options.append(templates.theme_element_background % color(key, value["background"], True))
                if "italic" in value and value["italic"]:
                    fontstyle.append("italic")
                if "bold" in value and value["bold"]:
                    fontstyle.append("bold")
                if "whole-word" in value and value["whole-word"]:
                    whole_word = True
                if "case-insensitive" in value and value["case-insensitive"]:
                    case_insensitive = True

                if len(fontstyle) > 0:
                    options.append(templates.theme_element_fontstyle % ' '.join(fontstyle))

            keyname = strip_non_alpha(regex)

            if whole_word or keyname == regex:
                # regex is completely alphabetical;
                # automatically enforce word boundary
                regex = "\\b%s\\b" % regex
            if case_insensitive:
                regex = "(?i:%s)" % regex
            keyname = "%s_%d" % (keyname, count)
            count = count + 1

            keywords.append(templates.keyword % (regex, keyname))
            theme_scopes.append(templates.theme_element % (keyname, keyname, ''.join(options)))

        keywords = ''.join(keywords)
        # print(keywords)
        # keywords = xml strings containing all the data already
        theme_scopes = ''.join(theme_scopes)
        scope_extensions = ''.join([(templates.additional_extension % x) for x in extensions])
        settings_extensions = ', '.join([(templates.additional_settings_extension % x) for x in extensions])
        other_settings = ''.join([templates.other_settings % (key, settings_map[key]) for key in list(settings_map.keys())])

        # produce output files
        ensure_directory_exists(SYNESTHESIA_OUTPUT_PATH)

        scope_filename = os.path.join(SYNESTHESIA_OUTPUT_PATH, theme_name + ".tmLanguage")
        theme_filename = os.path.join(SYNESTHESIA_OUTPUT_PATH, theme_name + ".tmTheme")
        settings_filename = os.path.join(SYNESTHESIA_OUTPUT_PATH, theme_name + ".sublime-settings")
        write_file(scope_filename, templates.scope % (scope_extensions, theme_name, keywords, "source" if autocompletion else "text", theme_name, uuid.uuid4()))
        # print(os.path.dirname(os.path.realpath(__file__)))
        print("Written to %s." % scope_filename)
        write_file(theme_filename, templates.theme % (theme_name, self.default_colors, theme_scopes, uuid.uuid4()))
        print("Written to %s." % theme_filename)
        write_file(settings_filename, templates.default_settings % (SYNESTHESIA_OUTPUT_PATH_RELATIVE, theme_name, settings_extensions, other_settings))
        print("Written to %s." % settings_filename)
