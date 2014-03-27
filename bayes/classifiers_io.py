import os
import math
from collections import defaultdict

import lex.oed.thesaurus.thesaurusdb as tdb
from .thesclasscache import ThesclassCache


def options_list(**kwargs):
    """
    Return the list of thesaurus class IDs that will be used as
    the set of options for the classifier to pick.
    """
    # Classifiers will only be built for thesaurus branches between these sizes
    branch_size_min = kwargs.get('min_size', 2500)
    branch_size_max = kwargs.get('max_size', 50000)

    return [t.id for t in tdb.taxonomy(level=5) if
            t.level in (2, 3, 4, 5) and t.wordclass is None and
            t.branch_size <= branch_size_max and
            (t.level == 2 or t.branch_size >= branch_size_min)]


def write_classifiers(dir, thesaurus_ids, features, number_of_senses,
                      total_senses):
    thesclass_cache = ThesclassCache()

    # Clear any existing files
    for f in os.listdir(dir):
        os.unlink(os.path.join(dir, f))

    # Build a probability table for each thesaurus class in turn
    for id in thesaurus_ids:
        thesclass = thesclass_cache.retrieve_thesclass(id)
        probabilities = []
        for feature, counts in features.items():
            if id in counts:
                count = counts[id]
            else:
                count = 0
            # Add 0.1 to everything to avoid zero values.
            probability = (count + 0.1) / (number_of_senses[id] + 0.1)
            probabilities.append((feature, probability))

        # Sort probabilities so that highest is first - not strictly
        #   necessary, but helps to make the output files easier to scan by
        #   eye for diagnostics, etc.
        probabilities.sort(key=lambda p: p[1], reverse=True)

        # Calculate prior probability for this thesaurus class.
        # Add 0.1 to everything to correspond with prob. estimation above.
        prior_probability = (number_of_senses[id]+0.1) / (total_senses+0.1)

        # Write it all to file.
        # Note that we store the *log* or each probability, rather than
        #   the raw probability itself. This is to guard against
        #   underflow problems.
        filepath = os.path.join(dir, '%d.txt' % id)
        headers = (thesclass.breadcrumb(), 'ID=%d' % id,
                   'LEVEL=%d' % thesclass.level,
                   'PRIOR_PROBABILITY=%f' % math.log(prior_probability))
        with open(filepath, 'w') as filehandle:
            for h in headers:
                filehandle.write('# ' + h + '\n')
            for p in probabilities:
                line = '%s\t%f\t%f\n' % (p[0], math.log(p[1]), p[1])
                filehandle.write(line)


def write_priors_file(in_dir, out_file):
    """
    Write a file listing each class and its log(prior probability),
    drawing on the information previously stored in the classifiers.
    This provides a quick way to load all the prior probabilities into
    memory without the overhead of loading the full classifiers.
    """
    prior_probabilities, keywords = load_classifiers(in_dir)
    priors = [(id, prior) for id, prior in prior_probabilities.items()]
    priors.sort(key=lambda p: p[0])
    with open(out_file, 'w') as filehandle:
        for p in priors:
            filehandle.write('%d\t%f\n' % p)


def load_classifiers(dir, mode='log'):
    prior_probabilities = {}
    keywords = defaultdict(dict)
    for f in [f for f in os.listdir(dir) if f.endswith('.txt')]:
        # Get the thesaurus ID from the filename
        id = int(f.split('.')[0])

        filepath = os.path.join(dir, f)
        with open(filepath, 'r') as filehandle:
            lines = [l.strip() for l in filehandle.readlines()]
        for l in lines:
            if l.startswith('#'):
                if 'PRIOR_PROBABILITY' in l:
                    prior_probabilities[id] = float(l.split('=')[1])
            else:
                keyword, log_probability, raw_probability = l.split('\t')
                if mode == 'log':
                    keywords[keyword][id] = float(log_probability)
                elif mode == 'raw':
                    keywords[keyword][id] = float(raw_probability)

    return prior_probabilities, keywords


def load_priors(in_file):
    priors = {}
    with open(in_file) as filehandle:
        for line in filehandle:
            id, prior = line.strip().split('\t')
            priors[int(id)] = float(prior)
    return priors
