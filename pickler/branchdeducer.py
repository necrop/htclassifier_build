import lex.oed.thesaurus.thesaurusdb as tdb

# abstract properties, relative properties, colour
USELESS_BRANCHES = (111290, 82596, 67134)


class BranchDeducer(object):

    def __init__(self):
        pass

    def branches_from_xrefs(self, sense):
        branches = set()
        for xr in sense.cross_references:
            instances = tdb.ranked_search(refentry=xr.refentry, refid=xr.refid)
            local_branches = _parse_instances(instances)
            branches = branches | local_branches
        return [b.id for b in branches]


def _parse_instances(instances):
    local_branches = set()
    if instances and tdb.distinct_senses(instances) <= 2:
        # Filter to just instances from the first sense that have
        #   a thesaurus class attached
        instances = [i for i in instances if i.refid == instances[0].refid
                     and i.thesclass is not None]

        # Get the set of level-3 ancestor branches covering the set of
        #  instances
        for i in instances:
            branch = i.thesclass.ancestor(level=3)
            if branch is not None:
                local_branches.add(branch)

    # Nix it if too many branches (>3) have emerged from this set of
    #  instances - which suggests that the underlying sense is too vague
    #  to be relied on
    if len(local_branches) > 3:
        local_branches = ()

    # Drop anything in the abstract properties and relative properties
    #  branches - these aren't very useful
    return set([b for b in local_branches if not _is_useless(b)])


def _is_useless(thesclass):
    for id in USELESS_BRANCHES:
        if thesclass.id == id or thesclass.is_descendant_of(id):
            return True
    if thesclass.wordclass is not None:
        return True
    return False
