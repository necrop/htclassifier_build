
import os

from regexcompiler import ReplacementListCompiler
import classifierconfig


DIRECTORY = os.path.join(classifierconfig.RESOURCES_DIR, 'compounds', 'clusters')

WORDCLASSES = ('NN', 'JJ', 'RB', 'first')

LIGHT_STEMMER = ReplacementListCompiler((
    (r'(y|ies|ie)$', r'i'),
    (r'sses$', r'ss'),
    (r'([^s])s$', r'\1'),
))
