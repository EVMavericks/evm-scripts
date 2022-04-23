import json
import requests
import os
import copy

DEFAULT_IPFS_GATEWAY = "https://gateway.ipfs.io/ipfs"
EVM_IPFS_ADDRESS = "QmNpw6kYTQNfU7LTsbj4zrFfCN8Ck4m1reUdNE63VBiNj2"
NUM_LIONS = 1324
DEFAULT_LION_CACHE_FILE = "lions.json"

# Most of these are reverse engineered by seeing which trait_types these values usually fall under
# The final 3 are the special eyes for the matrix lions, none were properly labeled as "Eyes" but it makes sense
MISSING_TRAIT_TYPE_REMAP = {
    "Scar" : "Accessory",
    "Green Shades" : "Eyes",
    "Tongue" : "Accessory",
    "Thug Life Glasses" : "Eyes",
    "Cigar" : "Accessory",
    "Green Headphones" : "Headwear",
    "White Eyes" : "Eyes",
    "Rainbow Headband" : "Headwear",
    "Blue Bandana" : "Headwear",
    "Pilot Helmet" : "Headwear",
    "Eyepatch" : "Eyes",
    "Laser Eyes" : "Eyes",
    "Yellow Headphones" : "Headwear",
    "Clown Nose" : "Accessory",
    "Green Bandana" : "Headwear",
    "Cyberpunk Headphones" : "Headwear",
    "Pink Bandana" : "Headwear",
    "Red Bandana" : "Headwear",
    "Neon Green Eyes" : "Eyes",
    "Matrix VR" : "Eyes",
    "3D Glasses Matrix" : "Eyes",
    "Blank" : "BLANK PLACEHOLDER"
}

# Gets the metadata for a lion off of IPFS, via some IPFS gateway
def getLion(lion_id, ipfs_gateway=DEFAULT_IPFS_GATEWAY):
    request_url = ipfs_gateway + "/" + EVM_IPFS_ADDRESS + "/" + str(lion_id)
    r = requests.get(request_url)
    r.raise_for_status()
    return json.loads(r.text)

# Gets all the lions in one ordered list
# By default will cache the resulting strucutre in lions.json in the local directory, and read from it on future calls instead of pulling from IPFS
def getAllLions(ipfs_gateway=DEFAULT_IPFS_GATEWAY, lion_cache_file=DEFAULT_LION_CACHE_FILE, force_refresh=False, write_cache=True, progress=False):
    # Check for presence of cache in current directory
    if os.path.exists(lion_cache_file) and not force_refresh:
        with open(lion_cache_file, 'r') as lionf:
            lions = json.load(lionf)
        return lions

    # General case: fetch all from ipfs
    lions = []
    for i in range(NUM_LIONS):
        if progress and i % 10 == 0:
            print("Downloading lion #" + str(i) + "/" + str(NUM_LIONS))
        lions.append(getLion(i, ipfs_gateway))

    # Write to cache if requested to avoid fetching the whole thing all the time
    if write_cache:
        with open(lion_cache_file, 'w') as lionf:
            json.dump(lions, lionf, sort_keys=True)
    return lions

# Computes the sum of each attribute of each type
def countAttributes(lions):
    traits = {}
    for lion in lions:
        for attribute in lion["attributes"]:
            # Some attributes don't have trait types, assign them as unspecified
            trait_type = attribute.get("trait_type", "Unspecified")

            # All should have values though
            value = attribute["value"]

            # Insert into traits dict, filling out the tree as needed
            if trait_type not in traits:
                traits[trait_type] = {}
            if value not in traits[trait_type]:
                traits[trait_type][value] = 0

            # Accumulate
            traits[trait_type][value] += 1
    return traits

# Based on ComradePotato's overview: https://discord.com/channels/963992696387694592/966603495589425192/967074502271967282
# There are some assumptions in these suggestions I'd like to be able to double check
def checkAssumptions(lions):
    for lion in lions:
        attrs = lion["attributes"]
        # 1: Accessory, Accessories, and Perk all cover the same things. Do any lions have more than one of these?
        if "Accessory" in attrs and "Accessories" in attrs:
            print("Warning: Lion " + str(lion["name"]) + " has Accessory " + attrs["Accessory"] + " and Accessories " + attrs["Accessories"])
        if "Accessory" in attrs and "Perk" in attrs:
            print("Warning: Lion " + str(lion["name"]) + " has Accessory " + attrs["Accessory"] + " and Perk " + attrs["Perk"])
        if "Perks" in attrs and "Accessories" in attrs:
            print("Warning: Lion " + str(lion["name"]) + " has Perk " + attrs["Perk"] + " and Accessories " + attrs["Accessories"])

        # 2: Headphones and Headwear all cover the same things. Do any lions have more than one of these?
        if "Headwear" in attrs and "Headphones" in attrs:
            print("Warning: Lion " + str(lion["name"]) + " has Headwear " + attrs["Headwear"] + " and Headphones " + attrs["Headphones"])

        # 3: Mohawk and Mohawk-Black are the same, apparantly all Mohawk-Blacks have the black background
        if "Mohawk" in attrs and attrs["Mohawk"] == "Mohawk - Black":
            if "Background" in attrs and attrs["Background"] == "Black Background":
                pass
            else:
                print("Warning: Lion " + str(lion["name"]) + " has Mohawk - Black but not a Black Background!")

        # 4: "Red shades (Zombie)" are only on OGs?
        if "Eyes" in attrs and attrs["Eyes"] == "Red Shades (Zombie)":
            if "Lion" in attrs and attrs["Lion"] != "OG Lion":
                print("Warning: Lion " + str(lion["name"]) + " has Red Shades (Zombie) but is not OG!")

    # 5: Missing trait_types. Do they have a clear category they can be assigned to?
    counts = countAttributes(lions)
    missing_trait_types = counts["Unspecified"]
    for value in missing_trait_types:
        possible_types = 0
        for trait_type in counts.keys():
            # Only check Accessory, since Accessories and Perk are the same
            # Also ignore Unspecified since that's what we're checking from
            if trait_type in ["Accessories", "Perk", "Unspecified"]:
                continue

            if value in counts[trait_type]:
                print(value + " can fit in as a " + trait_type)
                possible_types += 1
        if possible_types == 0:
            print("Warning: No matching trait_type for value " + value)

# Cleans up the metadata of a given lion
# Modifies the lion in place, make a deepcopy first if you want to avoid this
# Based on ComradePotato's overview: https://discord.com/channels/963992696387694592/966603495589425192/967074502271967282
# Bonus: Fix background name consistency
def cleanMetadata(lion):
    attrs = lion["attributes"]

    # 5a: Assign missing trait types
    # Do this first so other steps can count on trait_type being present
    # This will assign anything with the value Blank to the trait_type BLANK_PLACEHOLDER, but they'll be removed later
    for attr in attrs:
        if "trait_type" not in attr:
                attr["trait_type"] = MISSING_TRAIT_TYPE_REMAP[attr["value"]]

    # Build a more convenient dictionary with mapping from trait_type : value
    # We'll modify this, then convert back to the original format
    attrdict = {}
    for attr in attrs:
        attrdict[attr["trait_type"]] = attr["value"]

    # 1: Merge Accessory, Accessories, and Perk into Accessory
    if "Accessories" in attrdict:
        attrdict["Accessory"] = attrdict["Accessories"]
        del attrdict["Accessories"]
    if "Perk" in attrdict:
        attrdict["Accessory"] = attrdict["Perk"]
        del attrdict["Perk"]

    # 2: Merge Headphones into Headwear
    if "Headphones" in attrdict:
        attrdict["Headwear"] = attrdict["Headphones"]
        del attrdict["Headphones"]

    # 3a: Change Mohawk - Black to Mohawk
    if "Mohawk" in attrdict and attrdict["Mohawk"] == "Mohawk - Black":
        attrdict["Mohawk"] = "Mohawk"

    # 3b: Move special mohawks from Headwear to Mohawk
    if "Headwear" in attrdict and attrdict["Headwear"] in ["Matrix Mohawk", "Zombie Mohawk", "Cyberpunk Mohawk"]:
        attrdict["Mohawk"] = attrdict["Headwear"]
        del attrdict["Headwear"]

    # 4: Change Red Shades (Zombie) to Red Shades
    if "Eyes" in attrdict and attrdict["Eyes"] == "Red Shades (Zombie)":
        attrdict["Eyes"] = "Red Shades"

    # 5b: Remove Blanks
    for attr in list(attrdict.keys()):
        if attrdict[attr] == "Blank":
            del attrdict[attr]

    # Bonus B1: Change "Black Background" to "Black"
    if "Background" in attrdict and attrdict["Background"] == "Black Background":
        attrdict["Background"] = "Black"

    # Convert nice dictionary back to original format
    fmt_attrs = []
    for attr in attrdict:
        fmt_attrs.append({"trait_type":attr,"value":attrdict[attr]})
    lion["attributes"] = fmt_attrs

    return lion

# Cleans the metadata for an entire list of lions
# Modifies metadata in place, so make a deepcopy if you want to keep the original
def cleanAllMetadata(lions):
    for lion in lions:
        cleanMetadata(lion)
    return lions
    
if __name__ == "__main__":
    lions = getAllLions(progress=True)
    cleanLions = cleanAllMetadata(copy.deepcopy(lions))
    with open("cleanLions.json", "w") as outfile:
        json.dump(cleanLions, outfile, sort_keys=True, indent=2)
