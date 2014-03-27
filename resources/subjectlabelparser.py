from lxml import etree

# Only bother with labels with a frequency above this value
min_frequency = 50


class SubjectLabelParser(object):
    """
    Manages the subject label mapping and ontology.

    This effectively recomputes the subject-label characteristics for a given
    sense, by parsing any surface labels found in the sense or in its headers
    and returning the corresponding ontology nodes.

    We have to do this, rather than using the existing ch_subject values,
    because the ch_subject values are not independent of thesaurus
    classifications (for senses that have a thesaurus classification).
    So using the existing ch_subject values would screw up the training data.
    """

    nodes = {}
    node_map = {}

    def __init__(self, file=None):
        if not SubjectLabelParser.nodes:
            self._load_nodes(file)

    def _load_nodes(self, file):
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(file, parser)
        for c in tree.findall('.//class'):
            name = c.findtext('./name')
            size = int(c.findtext('./data/num_branch'))
            ancestors = [name,] # ancestors should include the current node
            ancestors.extend([p.findtext('./name') for p in
                c.iterancestors() if p.tag == 'class'])
            SubjectLabelParser.nodes[name] = {'name': name,
                'size': size, 'ancestors': ancestors}

            # Build a map so that each surface form points to this node
            surface_forms = c.findall('./data/forms/f')
            surface_forms = set([f.text.lower().strip(' .,')
                                 for f in surface_forms])
            surface_forms.add(name.lower().strip(' .,'))
            for f in surface_forms:
                SubjectLabelParser.node_map[f] = SubjectLabelParser.nodes[name]

        # Filter the set of ancestors for each node, so that only those
        #  over minsize are retained
        for node in SubjectLabelParser.nodes.values():
            ancestors_filtered = [a for a in node['ancestors'] if
                SubjectLabelParser.nodes[a]['size'] >= min_frequency]
            node['ancestors'] = ancestors_filtered

    def map_label_to_nodes(self, surface_form):
        """Returns the set of node labels corresponding to a given
        surface form.

        Returns an empty list if the surface form is not in the subject
        ontology.
        """
        surface_form = surface_form.lower().strip(' .,')
        if surface_form in SubjectLabelParser.node_map:
            node = SubjectLabelParser.node_map[surface_form]
            return node['ancestors']  #?? return set((node['name'],))
        else:
            return []

