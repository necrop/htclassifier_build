
from __future__ import division
import os
import numpy

from lex.oed.projects.thesaurus.classifier.config import ThesaurusConfig
from lex.oed.projects.thesaurus.classifier.bayes.classifiers_io import load_classifiers

config = ThesaurusConfig()
dir = os.path.join(config.get('paths', 'resources_dir'), 'bayes', 'classifiers')


def variation(scores):
    mean = numpy.mean(scores)
    max_deviation = max([abs(max(scores)-mean), abs(min(scores)-mean)])
    return max_deviation / mean

prior_probabilities, classifiers = load_classifiers(dir, mode='raw')
keywords = [(keyword, variation(scores.values())) for keyword, scores in
    classifiers.items() if keyword.startswith('T')]

# Look for the smallest deviation between average and max/min value
keywords.sort(key=lambda k: k[1])
for k in keywords[0:300]:
    print repr(k[0]), repr(k[1])
