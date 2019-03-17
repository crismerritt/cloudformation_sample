# CloudFormation parameters must be strictly alphanumeric; they may not have dashes or underscores.
# this function converts a tag name such as 'repo-url' to a CloudFormation parameter for a given tier.
# e.g. tag_name_to_param_name('spa', 'repo-url') => 'spaRepoUrl'


def tag_name_to_param_name(tier, tag):
    return tier + tag.title().replace('-', '').replace(' ', '')
