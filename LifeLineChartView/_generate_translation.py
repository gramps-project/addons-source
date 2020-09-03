import os
import copy
import re
import json
import life_line_chart
from glob import glob
from life_line_chart import AncestorChart, DescendantChart, BaseChart

DATA_FILES = [
    os.path.join(life_line_chart.__path__[0], 'BaseChartStrings.json'),
    os.path.join(life_line_chart.__path__[0], 'AncestorChartStrings.json'),
    os.path.join(life_line_chart.__path__[0], 'DescendantChartStrings.json')
]
DATA_STRUCTURES = dict([(a, json.loads(open(a,'r').read())) for a in DATA_FILES])
LIFE_LINE_CHART_LANGUAGES = list(list(DATA_STRUCTURES.values())[0].keys())
LIFE_LINE_CHART_LANGUAGES_SHORT = [a[:2] for a in LIFE_LINE_CHART_LANGUAGES]


## generate dummy.py
def iterate_containers(lang, handle_data, containers):
    for container in containers:
        for group, group_item in container[lang].items():
            for gui_name, gui_item in group_item.items():
                for string_name, data in gui_item.items():
                    handle_data(container, lang, group, gui_name, string_name, data)
f = open(os.path.join(os.path.dirname(__file__), '_dummy_translation_string_po.py'),'w',encoding='utf-8-sig')
f.write("""# Do not edit! This file was generated using _generate_translation.py

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

""")
def handle_data(container, lang, group, gui_name, string_name, data):
    if string_name == 'choices':
        for choice, choice_string in data.items():
            f.write('_("' + choice_string.replace('"','\\"') + '")\n')
    else:
        f.write('_("' + data.replace('"','\\"') + '")\n')
iterate_containers(
    'en_US.UTF-8',
    handle_data,
    DATA_STRUCTURES.values()
    )
f.close()


## update po files
def set_or_get_translation(string, lang, new_value = None, set_overwrites=False):
    try:
        def get_translated_string(container, lang, group, gui_name, string_name, data):
            data_en = container['en_US.UTF-8'][group][gui_name][string_name]
            if string_name == 'choices':
                for (choice_name, choices_data), choice_data_en in zip(data.items(), data_en.values()):
                    if string == choice_data_en:
                        if new_value is not None:
                            if set_overwrites or data[choice_name] == string:
                                # change if unset or overwrite true
                                data[choice_name] = new_value
                        else:
                            raise RuntimeError(choices_data)
            elif string == data_en:
                if new_value is not None:
                    if set_overwrites or container[lang][group][gui_name][string_name] == string:
                        # change if unset or overwrite true
                        container[lang][group][gui_name][string_name] = new_value
                else:
                    raise RuntimeError(data)
        iterate_containers(
            lang,
            get_translated_string,
            DATA_STRUCTURES.values()
            )
    except Exception as e:
        return str(e)
    return None

for lang in LIFE_LINE_CHART_LANGUAGES:
    filename = os.path.join(os.path.dirname(__file__), 'po', lang[:2] + '-local.po')
    if os.path.isfile(filename):
        content = open(filename,'r',encoding='utf-8-sig').read()
        if content[-2:] !='\n\n':
            content += '\n'
        if content[-2:] !='\n\n':
            content += '\n'
        items = re.findall(r'(\nmsgid ((?:"(?:[^"]|\\")*"\n)+))(msgstr ((?:"(?:[^"]|\\")*"\n)+)\n)', content)
        translations = dict([(i[1].replace('"\n"','')[1:-2], i) for i in items])

        for original_string, (original_line, original_msg, translated_line, translated_msg) in translations.items():
            if original_string != '':
                t = set_or_get_translation(original_string, lang)
                if t is not None:
                    content = content.replace(original_line + translated_line, original_line + 'msgstr "'+t+'"\n\n')

        f=open(filename,'w',encoding='utf-8')
        f.write(content)
        f.close()


# update life_line_chart module
# for filename in glob(os.path.join(os.path.dirname(__file__), 'po','??-local.po')):
#     basename = os.path.basename(filename)
#     first, extension = os.path.splitext(basename)
#     lang_short = first[:2]
#     if lang_short in LIFE_LINE_CHART_LANGUAGES_SHORT:
#         lang = LIFE_LINE_CHART_LANGUAGES[LIFE_LINE_CHART_LANGUAGES_SHORT.index(lang_short)]
#         # print (basename)
#         content = open(filename,'r',encoding='utf-8-sig').read()
#         if content[-2:] !='\n\n':
#             content += '\n'
#         if content[-2:] !='\n\n':
#             content += '\n'
#         items = re.findall(r'(\nmsgid ((?:"(?:[^"]|\\")*"\n)+))(msgstr ((?:"(?:[^"]|\\")*"\n)+)\n)', content)
#         translations = dict([(i[1].replace('"\n"','')[1:-2], i) for i in items])

#         for original_string, (original_line, original_msg, translated_line, translated_msg) in translations.items():
#             if original_string != '':
#                 set_or_get_translation(original_string, lang, translated_msg.replace('"\n"','')[1:-2])
#         f.close()

# for filename, structure in DATA_STRUCTURES.items():
#     with open(filename,'w') as f:
#         json.dump(structure, f, indent=4)
