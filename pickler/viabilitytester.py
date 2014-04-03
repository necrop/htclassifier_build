
import re
from regexcompiler import ReplacementListCompiler

cleaner = ReplacementListCompiler((
    (r'\. (obs\.|obs\. rare\.|rare\.|now rare\.|hist\.|hist\. rare\.)$', ''),
    (r'\.', '')
))

trigger_words = {'proverb', 'miscellaneous', 'phrases', 'error', 'erroneous'}
trigger_definitions = {'fig', 'transf and fig',
                       'fig or in fig contexts', 'fig and in fig contexts',
                       'fig and in extended use', 'general uses',
                       'in extended use', 'extended uses',
                       'in general use', 'intr', 'trans'}


def is_viable(sense):
    if sense.num_lemmas >= 3:
        return False
    if sense.is_affix():
        return False
    if sense.wordclass not in ('NN', 'JJ', 'RB', 'VB', 'UH', 'PHRASE'):
        return False
    if sense.equals_crossreference():
        return True
    if sense.definition is None:
        return True

    d = clean_definition(sense.definition)
    g = sense.gloss.lower()
    if (d.startswith('general attrib') or
            d.startswith('gen attrib') or
            d.startswith('appositive') or
            d.startswith('comb, ') or
            d.startswith('comb ') or
            d == 'comb'):
        return False

    if any([t in d for t in trigger_words]):
        return False
    if d in trigger_definitions or g in trigger_definitions:
        return False
    if re.search(r'^with (to|for|by|complement)$', d):
        return False

    return True


def clean_definition(d):
    d = cleaner.edit(d.lower())
    d = d.strip('.;: ')
    return d
