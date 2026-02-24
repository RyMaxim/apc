from apc.logging_config import get_logger

logger = get_logger(__name__)

import csv
import json
import re
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from string import digits

import pyautogui

from apc import adf, config, populations, utils
from apc.adf import AdfAnimal, LoadedReserve
from deca.ff_rtpc import RtpcNode, rtpc_from_binary
from deca.hashes import hash32_func

ANIMAL_DETAILS_FILE = Path(config.CONFIG_PATH / "animal_details.json")
ANIMAL_NAMES_FILE = Path(config.CONFIG_PATH / "animal_names.json")
FUR_NAMES_FILE = Path(config.CONFIG_PATH / "fur_names.json")

class RtpcAnimal:
  __slots__ = ("species_id", "name", "full_name", "ammo_class", "truracs", "great_one", "scoring_data", "fur_data", "fur_details")

  species_id: int
  name: str
  full_name: str
  ammo_class: int
  truracs: bool
  great_one: bool
  scoring_data: dict[str, dict]
  fur_data: list
  fur_details: dict

  def __init__(self, animal_node: RtpcNode) -> None:
    prop_data = RtpcAnimal._parse_prop_table(animal_node)
    self.species_id = prop_data["species_id"]
    self.name = prop_data["name"]
    try:
      self.full_name = prop_data["full_name"]
    except:
      print(f"No 'full_name' for {self.name}")
    self.ammo_class = prop_data["ammo_class"]
    self._parse_scoring_data(animal_node)
    self._parse_fur_data(animal_node)

  def to_dict(self):
    return {slot: getattr(self, slot) for slot in self.__slots__}

  @staticmethod
  def _parse_prop_table(node: RtpcNode) -> dict:
    prop_hashes = {
      431526284: "species_id",        # 0x19b8918c - animal
      343126393:  "_class",           # "_class" 0x1473b179
      1986754702: "full_name",        # 0x766b788e - animal
      3541743236: "name",             # "name" 0xd31ab684
      1776847959: "gender",           # "gender" 0x69e88c57
      3489629189: "_object_id",       # "_object_id" 0xcfff8405
      662736202:  "ammo_class",       # 0x27808d4a - animal
      3667945025: "great_one",        # 0xdaa06641 - scoring
      703742452:  "weight_high",      # 0x29f241f4 - scoring
      2280276680: "weight_low",       # 0x87ea42c8 - scoring
      3808832014: "score_high",       # 0xe3062a0e - scoring
      335972312:  "score_low",        # 0x140687d8 - scoring
      3913613897: "weight_bias",      # 0xe9450249 - scoring
      2895764937: "rack_balance",     # 0xac99ddc9 - scoring
      3954305432: "rack_randomness",  # 0xebb1e998 - scoring
      1944770169: "index",            # "index" 0x73ead679 - fur
      4080448159: "variation_name",   # 0x00001378 - fur
      3634380208: "probability",      # 0xd8a03db0 - fur
      3358259124: "rarity",           # 0xc82af7b4 - fur
      3943955667: "great_one",        # 0xeb13fcd3 - fur
      496795291:  "male_modelc",      # 0x1d9c7e9b - fur
      1728140822: "female_modelc",    # 0x67015616 - fur
      3715423160: "diffuse_texture",  # "diffuse_texture" 0xdd74dbb8 - fur
    }
    prop_data = {}
    for prop in node.prop_table:
      if (prop_name := prop_hashes.get(prop.name_hash)):
        value = prop.data
        if isinstance(value, bytes):
          value = value.decode("utf-8")
        prop_data[prop_name] = value
    return prop_data

  @staticmethod
  def _get_table(animal_node: RtpcNode, table_type: str) -> RtpcNode:
    table_classes = {
      "scoring": "CAnimalTypeScoringSettings",
      "fur": "CAnimalTypeVisualVariationSettings",
      "clue": "CAnimalTypeClueSettings",
      "spawn_tags": "CAnimalTypeSpawnTags",
      "spawn_around_player": "SAnimalTypeSpawnAroundPlayerSettings",  # birds
    }
    for table in animal_node.child_table:
      prop_data = RtpcAnimal._parse_prop_table(table)
      if prop_data.get("_class") in table_classes[table_type]:
        return table
    return None

  def _parse_scoring_data(self, animal_node: RtpcNode) -> None:
    self.scoring_data = {}
    self.truracs = False
    self.great_one = False
    scoring_table = RtpcAnimal._get_table(animal_node, "scoring")
    if scoring_table is None:
      return
    for scoring_node in scoring_table.child_table:
      prop_data = RtpcAnimal._parse_prop_table(scoring_node)
      if prop_data.get("_class") == "SAnimalTypeScoringDistributionSettings":
        gender = "male" if prop_data["gender"] == 0 else "female"
        if prop_data["great_one"] == 1:
          self.great_one = True
          gender = f"great_one_{gender}"
        self.scoring_data[gender] = prop_data
      if prop_data.get("_class") == "SAnimalTypeScoringFeatureData":
        self.truracs = True
    gender_order = ["male", "female", "great_one_male", "great_one_female"]
    self.scoring_data = {key: self.scoring_data[key] for key in gender_order if key in self.scoring_data}

  def _parse_fur_data(self, animal_node: RtpcNode) -> None:
    self.fur_data = []
    fur_table = RtpcAnimal._get_table(animal_node, "fur")
    if fur_table is None:
      return
    for fur_node in fur_table.child_table:
      prop_data = RtpcAnimal._parse_prop_table(fur_node)
      if prop_data.get("_class") == "SAnimalTypeVisualVariation":
        if prop_data["great_one"] == 1:
          self.great_one = True
        self.fur_data.append(prop_data)
      if "variation" in prop_data:
        if "variation" not in prop_data["variation"]:
          logger.error(f"ANIMAL: {self.name}   FUR: {prop_data['name']}   VARIATION: {prop_data['variation']}")
        if prop_data["variation"] != f"variation_{prop_data["index"]}":
          logger.error(f"ANIMAL: {self.name}   FUR: {prop_data['name']}   INDEX {prop_data['index']} NOT EQUAL VARIATION {prop_data['variation']}")

class RtpcReserve:
  __slots__ = ("reserve_id", "name", "full_name", "species_ids", "species_details")

  reserve_id: int
  name: str
  full_name: str
  species_ids: list[int]
  species_details: dict

  def __init__(self, reserve_id: int, rtpc_data: RtpcNode) -> None:
    prop_data = RtpcAnimal._parse_prop_table(rtpc_data)
    self.reserve_id = reserve_id
    self.name = prop_data["name"]
    self.species_ids = self._parse_species_ids(rtpc_data)

  def to_dict(self):
    return {slot: getattr(self, slot) for slot in self.__slots__}

  def _get_table(self, rtpc_data: RtpcNode, table_name: str) -> RtpcNode:
    table_hashes = {
      498704821: "species",         # 0x1db9a1b5
      1021486167: "cold_effect",    # 0x3ce2a457
      2133761006: "textures",       # 0x7f2e9bee
      2487179630: "need_zones",     # 0x943f596e
      2749031136: "???",            # 0xa3dae2e0
      3050727908: "deployables",    # 0xb5d669e4
      3560954187: "dust_effect",    # 0xf0ae4365
      4037952357: "bitmaps",        # 0xfbdb5d56
    }
    for table in rtpc_data.child_table:
      if table_name == table_hashes.get(table.name_hash):
        return table
    return None

  def _parse_species_ids(self, rtpc_data: RtpcNode):
    species_ids = []
    species_data = self._get_table(rtpc_data, "species")
    if not species_data:
      raise ValueError("Unable to parse species table from resetve %s", self.reserve_id)
    for species_table in species_data.child_table:
      prop_data = RtpcAnimal._parse_prop_table(species_table)
      species_ids.append(prop_data["species_id"])
    return species_ids

def open_rtpc(filename: Path) -> RtpcNode:
  with filename.open("rb") as f:
    data = rtpc_from_binary(f)
  root = data.root_node
  return root

def get_global_animals() -> list[RtpcAnimal]:
  root = open_rtpc(config.GLOBAL_ANIMAL_TYPES)
  animal_data = root.child_table[0].child_table
  rtpc_animals = []
  for animal_node in animal_data:
    animal = RtpcAnimal(animal_node)
    if not animal.scoring_data or not animal.fur_data:
      continue
    rtpc_animals.append(animal)
    # print(f"parsed {animal.name}")
  rtpc_animals.sort(key=lambda a: a.name)
  return rtpc_animals

def export_animal_hashes_to_json() -> None:
  rtpc_animals = get_global_animals()
  animal_name_hashes = {}
  name_hashes = {}
  for a in rtpc_animals:
    animal_name_hashes[hash32_func(a.full_name)] = a.full_name
    name_hashes[hash32_func(a.name)] = a.name
  animal_name_hashes = {str(k): v for k, v in sorted(animal_name_hashes.items())}
  name_hashes = {str(k): v for k, v in sorted(name_hashes.items())}
  hash_map = {"animal_name": animal_name_hashes, "name": name_hashes}
  save_json(config.CONFIG_PATH / "species_hashes_2.json", hash_map)

class RtpcJSONEncoder(json.JSONEncoder):
  def default(self, o):
    return o.__dict__
    # return o.to_dict()

def format_animals(animal_list: list[RtpcAnimal]) -> dict:
  formatted_animals = {}
  for animal in animal_list:
    formatted_data = {
      "species_id": animal.species_id,
      "ammo_class": animal.ammo_class,
      "gender": defaultdict(dict),
    }
    for gender, fur_data in format_fur_data(animal).items():
      formatted_data["gender"][gender].update(fur_data)
    for gender, scoring_data in format_scoring_data(animal).items():
      if gender.startswith("great_one_") and scoring_data["score_low"] == 0:
        formatted_data["gender"].pop(gender, None)
        logger.warning(f"{animal.name} :: {gender} has invalid scoring data")
        continue
      formatted_data["gender"][gender].update(scoring_data)
    if animal.truracs:
      formatted_data["truracs"] = True
    formatted_data["trophy"] = calculate_trophy_scores(formatted_data)
    formatted_animals[animal.name] = formatted_data
  sorted_names = sorted([name for name in formatted_animals.keys()])
  return {name: formatted_animals[name] for name in sorted_names}

def format_fur_data(animal: RtpcAnimal) -> dict:
  formatted_data = {}
  merged_furs = merge_furs(animal.fur_data, animal.name)
  format_fur_keys(merged_furs, animal.name)
  for gender, furs_list in merged_furs.items():
    fur_total_probability = sum([fur["probability"] for fur in furs_list])
    fur_probabilities = {}
    for fur in furs_list:
      if fur["key"] in fur_probabilities:
        logger.critical(f'Fur "{fur['key']}" already in list for {animal.name} {gender}')
      fur_probabilities[fur["key"]] = fur["probability"]
    formatted_data[gender] = {"fur_total_probability": fur_total_probability, "furs": fur_probabilities}
    if (total_probability := sum(fur_probabilities.values())) != fur_total_probability:
      logger.critical(f"Total probability mismatch! {total_probability} should be {fur_total_probability}")
  gender_order = ["male", "female", "great_one_male", "great_one_female"]
  formatted_data = {key: formatted_data[key] for key in gender_order if key in formatted_data}
  return formatted_data

def merge_furs(fur_data: list[dict], animal_name: str) -> dict:
  def filter_furs(genders: list[int], great_one: bool, animal_name: str):
    filtered_furs = [fur for fur in fur_data if fur["gender"] in genders and fur["great_one"] == great_one]
    if (animal_name == "whitetail_deer" and great_one):
      # Whitetail Deer share the Tan, Brown, and Dark Brown visual variaions with their Great One
      # Fabled Piebald has a separate skin ("great_one_whitetail")
      whitetail_great_one_furs = [fur for fur in fur_data if fur["gender"] in genders and fur["variation_name"].endswith(("_tan", "_brown", "_dark_brown"))]
      filtered_furs.extend(whitetail_great_one_furs)
    return filtered_furs

  merged_furs = {}
  gender_data = {
    "male": {"genders": [0, 1], "great_one": False},
    "female": {"genders": [0, 2], "great_one": False},
    "great_one_male": {"genders": [0, 1], "great_one": True},
    "great_one_female": {"genders": [0, 2], "great_one": True},
  }
  for gender, data in gender_data.items():
    if gender_furs := filter_furs(data["genders"], data["great_one"], animal_name):
      # print(f"   Merged {len(sorted_furs)} {gender.replace("_", " ").title()} furs")
      merged_furs[gender] = gender_furs
  return merged_furs

def format_fur_keys(merged_furs: dict, animal_name: str):
  for gender, furs in merged_furs.items():
    seen = defaultdict(list)
    for i, fur in enumerate(furs):
      # There are many animals where multiple furs have the same "animal_visual_variation_<fur_name>" values
      # We cannot always just take that <fur_name> at face value as the fur name
      # Build a dict with <fur_name> as key and list of indexes that match as value
      fur["key"] = fur["variation_name"].removeprefix("animal_visual_variation_").rstrip(digits)
      seen[fur["key"]].append(i)
    for key, indexes in seen.items():
      # Go through each list of duplicates and attempt to parse other attributes for a valid/unique fur name
      if len(indexes) > 1:
        logger.debug(f"Duplicate Furs!   Animal: {animal_name}   Gender: {gender}   Fur: {key}   Indexes: {indexes}")
        for i in indexes:
          fur = furs[i]
          if manual_key_map := map_fur_key(fur, animal_name, gender):
            # Some furs are super edge cases that are unrealistic to parse programatically
            # map_fur_key() handles matching these
            logger.info(f"Mapped key '{manual_key_map}' for {animal_name} :: {gender} :: '{fur['key']}' :: Index {fur['index']}")
            fur["key"] = manual_key_map
            continue
          elif variant := get_fur_variant(fur, animal_name, gender):
            if variant.isdigit() and variant != "1":
              fur["key"] = fur["key"] + "_" + variant
            if not variant.isdigit():
              logger.error(f"Strange variant name: '{variant}'")
              continue
            logger.info(f"Parsed variant {variant} for {animal_name} :: {gender} :: '{fur['key']}' :: Index {fur['index']}")
          else:
            logger.error(f"Unable to parse fur variant for {animal_name} :: {gender} :: '{fur['key']}' :: Index {fur['index']}")

def get_fur_variant(fur: dict, animal_name: str, gender: str) -> str:
    if "diffuse_texture" in fur:
      texture_name = fur["diffuse_texture"].split("/")[-1].removesuffix("_dif.tga").removesuffix("_diff.tga")
      if variant := get_trailing_digit(texture_name):
        return variant
      if (variant := texture_name.split("_")[-1]) == fur["key"]:
        return "1"
    short_gender = gender.removeprefix("great_one_")
    if f"{short_gender}_modelc" in fur:
      model_name = fur[f"{short_gender}_modelc"].split("/")[-1].removesuffix(".modelc")
      if variant := get_trailing_digit(model_name):
        return variant
      if (variant := model_name.split("_")[-1]).endswith(fur["key"].replace("_","")):  # pseudo_melanistic_white > pseudomelanisticwhite
        return "1"
    return None

def get_trailing_digit(s):
    for char in reversed(s):
        if char.isdigit():
            return char
    suffixes = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
    }
    for word, digit in suffixes.items():
        if s.endswith(word):
            return digit
    logger.debug(f"No trailing digit for {s}")
    return None

def map_fur_key(fur: dict, animal_name: str, gender: str) -> str:
  # Wild Boar Great Ones have variant names that end in `_GO_x`
  if animal_name == "wild_boar" and gender.startswith("great_one_"):
    variant = get_trailing_digit(fur["variation_name"])
    return f"wild_boar_great_one_{variant}"

  # I hate doing any manual mapping but it's impossible to catch every edge-case in so here we are
  # Match on animal_name and "index" value (sane as b'variation_xx' value)

  fur_map = {
    "eastern_grey_kangaroo": {
      0: "grey",
    },
    "eurasian_brown_bear": {
      5: "albino_boss",
      7: "albino",
    },
    "fallow_deer": {
      0: "piebald_2",
      1: "dark",
      2: "spotted",
      10: "dark_2",
      12: "spotted_2",
      18: "piebald",
    },
    "feral_goat": {
      5: "dark_brown",
      8: "mixed",
      10: "white_brown",
    },
    "feral_pig": {
      2: "black_spots",
      9: "dark_brown",
      4: "dark_brown_2",
    },
    "goldeneye": {
      4: "hybrid_2",
      5: "hybrid_1",
    },
    "iberian_mouflon": {
      3: "brown",
      4: "brown_2",
    },
    "mule_deer": {
      4: "piebald_2",
      5: "piebald",
    },
    "northern_red_muntjac": {
      0: "red",
    },
    "rock_ptarmigan": {
      1: "mottled",
    },
    "springbok": {
      1: "black_brown_2",
    },
    "wild_yak": {
      8: "albino_2",
    },
  }
  if animal_furs := fur_map.get(animal_name):
    return animal_furs.get(fur["index"])
  return None

def format_scoring_data(animal: RtpcAnimal) -> dict:
  formatted_data = {}
  for gender in animal.scoring_data.keys():
    # if gender == "great_one_female":
    #   continue
    gender_data = animal.scoring_data[gender]
    formatted_data[gender] = {
      "score_low": round(gender_data["score_low"], 3),
      "score_high": round(gender_data["score_high"], 3),
      "weight_low": round(gender_data["weight_low"], 3),
      "weight_high": round(gender_data["weight_high"], 3),
    }
  return formatted_data

def save_json(file: Path, data: dict) -> None:
  file.write_text(json.dumps(data, indent=2, cls=RtpcJSONEncoder))

def seed_all_reserves() -> None:
  # Before seeding levels:
  #  1. set reserve population to 3x+ in Mod Builder and generate new pop files
  #  2. launch APS once and set the path to the "apc/mods" directory to load modded files
  update_global_animal_data()
  for reserve_key, _data in config.RESERVES.items():
    seed_reserve_animal_details(reserve_key, skip_update_fur=True)
  logger.info("[green]All reserves seeded![/green]")

def update_global_animal_data() -> None:
  animal_details = config.load_json(ANIMAL_DETAILS_FILE)
  logger.info(f"Loaded {len(animal_details)} animals from `animal_details.json`")
  rtpc_animals = get_global_animals()
  logger.info(f"Parsed {len(rtpc_animals)} animals from `global_animal_types.blo`")
  formatted_animals = format_animals(rtpc_animals)
  logger.info(f"Formatted RTPC animals")
  merge_animal_details(animal_details, formatted_animals)
  animal_details = dict(sorted(animal_details.items()))
  save_json(ANIMAL_DETAILS_FILE, animal_details)
  update_animal_names()
  update_fur_names()

def update_animal_names() -> dict:
  animal_names = config.load_json(ANIMAL_NAMES_FILE)
  animal_details = config.load_json(ANIMAL_DETAILS_FILE)
  for animal in animal_details.keys():
    if animal not in animal_names:
      animal_names[animal] = { "animal_name": utils.format_key(animal) }
  animal_names = dict(sorted(animal_names.items()))
  save_json(ANIMAL_NAMES_FILE, animal_names)

def update_fur_names() -> dict:
  fur_names = config.load_json(FUR_NAMES_FILE)
  animal_details = config.load_json(ANIMAL_DETAILS_FILE)
  for _animal, animal_data in animal_details.items():
    for _gender, gender_data in animal_data["gender"].items():
      for fur in gender_data["furs"].keys():
        if fur not in fur_names:
          fur_names[fur] = { "fur_name": utils.format_key(fur) }
  fur_names = dict(sorted(fur_names.items()))
  save_json(FUR_NAMES_FILE, fur_names)

def merge_animal_details(old_animal_details: dict, new_animal_details: dict) -> dict:
  for species, details in new_animal_details.items():
    if species not in old_animal_details:
      logger.info(f"[yellow]{species} not in save file[/yellow]")
      old_animal_details[species] = details
      continue
    # old_animal_details[name].pop("level", None)  # Uncomment to delete old "level" data
    # old_animal_details[name].pop("trophy", None)  # Uncomment to delete old "trophy" data
    for key in ["ammo_class", "animal_name", "gender", "level", "trophy", "truracs"]:
      if new_animal_details[species].get(key):
        old_animal_details[species][key] = new_animal_details[species][key]
    # always overwrite with new gender and species_id data
    old_animal_details[species]["gender"] = new_animal_details[species]["gender"]
    old_animal_details[species]["species_id"] = new_animal_details[species]["species_id"]
    old_animal_details[species] = dict(sorted(old_animal_details[species].items()))

def seed_reserve_animal_details(reserve_key: str, skip_update_fur: bool = False, skip_levels: bool = False) -> None:
  if not skip_update_fur:
    update_global_animal_data()
  logger.info(f"Seeding reserve '{reserve_key}': {config.get_reserve_name(reserve_key)} [animal_population_{config.get_population_reserve_key}]")
  animal_details = config.load_json(ANIMAL_DETAILS_FILE)
  reserve_species = config.get_reserve(reserve_key)["species"]
  for species_key in reserve_species: # slice like [2:5]
    species_config = animal_details.get(species_key)
    if not species_config:
      continue
      # raise ValueError(f"Unable to find data for speecies {species_key} on reserve {reserve_key}")
    if "level" not in species_config and not skip_levels:
      seeded_species_data = seed_species(reserve_key, species_key, species_config)
      if not seeded_species_data:
        continue
      species_config["level"] = seeded_species_data["level"]
    animal_details[species_key] = species_config
    sorted_animal_details = {key: animal_details[key] for key in sorted(animal_details)}
    save_json(ANIMAL_DETAILS_FILE, sorted_animal_details)

def trim_trailing_ranges(ranges: list[list]) -> list[list]:
  while ranges and not ranges[-1]:
    ranges.pop()

def seed_species(reserve_key: str, species_key: str, species_config: dict) -> dict:
  logger.info(f"Seeding species: {species_key}")
  loaded_reserve = LoadedReserve(reserve_key, parse=True)
  try:
    species_groups = populations._get_species_groups(reserve_key, loaded_reserve.parsed_adf.adf, species_key)
  except populations.NoAnimalsException:
    return None
  seeded_species_data = {}
  if "level" not in species_config or not species_config["level"]:
    logger.critical(f"No level data for {species_key}")
    seeded_species_data["level"] = seed_animal_levels(loaded_reserve, species_key, species_config, species_groups)
  else:
    logger.info(f"[green]Levels aready seeded for {species_key}[/green]")
  return seeded_species_data

def calculate_trophy_scores(species_config: dict) -> dict:
  '''
  Bronze: Bottom 20%
  Silver: 20% - 60%
  Gold: 60% - 90%
  Diamond: Top 10%
  '''
  genders = species_config["gender"]
  valid_scores = []
  valid_weights = []
  for gender, gdata in genders.items():
    if gender.startswith("great_one"):
      continue
    score_low = gdata.get("score_low", 0)
    score_high = gdata.get("score_high", 0)
    weight_low = gdata.get("weight_low", 0)
    weight_high = gdata.get("weight_high", 0)
    if all(x > 0 for x in (score_low, score_high, weight_low, weight_high)):
      valid_scores.append((score_low, score_high))
      valid_weights.append((weight_low, weight_high))
  if not valid_scores or not valid_weights:
    return None

  score_min = min(s[0] for s in valid_scores)
  score_max = max(s[1] for s in valid_scores)
  score_range = score_max - score_min

  weight_min = min(w[0] for w in valid_weights)
  weight_max = max(w[1] for w in valid_weights)
  weight_range = weight_max - weight_min

  def pct(v): return round(score_min + v * score_range, 3)
  def w_pct(v): return round(weight_min + v * weight_range, 3)

  silver_score_low = pct(0.20)
  gold_score_low = pct(0.60)
  diamond_score_low = pct(0.90)

  silver_weight_low = w_pct(0.20)
  gold_weight_low = w_pct(0.60)
  diamond_weight_low = w_pct(0.90)

  return {
      "bronze": {
          "score_low": round(score_min, 3),
          "score_high": round(silver_score_low - 0.001, 3),
          "weight_low": round(weight_min, 3),
          "weight_high": round(silver_weight_low - 0.001, 3),
      },
      "silver": {
          "score_low": silver_score_low,
          "score_high": round(gold_score_low - 0.001, 3),
          "weight_low": silver_weight_low,
          "weight_high": round(gold_weight_low - 0.001, 3),
      },
      "gold": {
          "score_low": gold_score_low,
          "score_high": round(diamond_score_low - 0.001, 3),
          "weight_low": gold_weight_low,
          "weight_high": round(diamond_weight_low - 0.001, 3),
      },
      "diamond": {
          "score_low": diamond_score_low,
          "score_high": round(score_max, 3),
          "weight_low": diamond_weight_low,
          "weight_high": weight_max,
      }
  }


def seed_animal_levels(
  loaded_reserve: LoadedReserve,
  species_key: str,
  species_config: dict,
  species_groups: list,
) -> list[list]:
  gender_configs = species_config["gender"]
  male, female = gender_configs["male"], gender_configs["female"]
  min_weight = min(male["weight_low"], female["weight_low"])
  max_weight = max(male["weight_high"], female["weight_high"])
  min_score = min(male["score_low"], female["score_low"])
  max_score = max(male["score_high"], female["score_high"])

  # seed the gender that scores diamonds to increase accuracy at the top end
  # if both can be diamond, pick the one with the heavier max weight
  diamond_gender = config.get_diamond_gender(species_key)
  if diamond_gender == "both":
    diamond_gender = max(gender_configs, key=lambda g: gender_configs[g]["weight_high"])
  gender = 1 if diamond_gender == "male" else 2

  logger.info(f"Seeding levels for {species_key}. Min weight: {min_weight} >> Max weight: {max_weight}")
  # initially just seed in 0.1kg increments to build overall levels
  # use 0.01kg granularity for small animals with max weight <10kg
  seed_unit = 100 if min_weight < 10 else 10
  seed = int(min_weight * seed_unit)
  max_seed = (max_weight + 1) * seed_unit
  levels = [[] for _ in range(9)]
  while seed <= max_seed:
    aps_levels, seed = seed_weights_and_process_aps(
      species_key,
      species_groups,
      loaded_reserve,
      seed,
      seed_unit,
      min_score,
      gender,
    )
    levels = merge_levels(levels, aps_levels)
    levels = sanitize_levels(levels, min_weight, max_weight)

  logger.info(f"Seeding precise levels for {species_key}")
  # seed animals in 0.001kg increments between levels to determine exact breakpoints
  seed_unit = 1000
  seed = 0
  max_seed = 0
  for i, values in enumerate(levels):
    if seed > max_weight * seed_unit or max_seed > max_weight * seed_unit:
      break
    if not values or values[1] >= max_weight:
      continue
    if seed > values[1] * seed_unit or max_seed > values[1] * seed_unit:
      continue
    seed = int(values[1] * seed_unit)
    max_seed = (values[1] + 1) * seed_unit
    aps_levels, _ = seed_weights_and_process_aps(
      species_key,
      species_groups,
      loaded_reserve,
      seed,
      seed_unit,
      min_score,
      gender,
    )
    levels = merge_levels(levels, aps_levels)
    levels = sanitize_levels(levels, min_weight, max_weight)

  trim_trailing_ranges(levels)
  logger.info(f"[green]Seeded levels:[/green] {levels}")
  return levels


def seed_weights_and_process_aps(
    species_key: str,
    species_groups: list,
    loaded_reserve: LoadedReserve,
    seed: int,
    seed_unit: int,
    min_score: int,
    gender: int,  # 1=male, 2=female
) -> tuple[list[list], int]:
    initial_seed = seed
    seed = seed_weights(
        species_key,
        species_groups,
        loaded_reserve.parsed_adf.decompressed.data,
        seed,
        seed_unit,
        min_score,
        gender,
    )
    aps_species_key = map_aps(loaded_reserve.reserve_key, species_key)
    logger.info(f"Seeding weight: [{initial_seed/seed_unit}-{seed/seed_unit}] {species_key} ({aps_species_key}) @ {loaded_reserve.reserve_key}")
    loaded_reserve.save()
    launch_aps()
    click_reserve(loaded_reserve.reserve_key)
    aps_levels = process_aps_levels(aps_species_key, Path("scans/scan.csv"), "weight")
    if not any(aps_levels):
        logger.critical(
            f"Didn't find any animal data; probably have name wrong: "
            f"{species_key.lower()}:{utils.unformat_key(aps_species_key).lower()}"
        )
        raise RuntimeError("APS scan returned no data")
    return aps_levels, seed


def merge_ranges(old: list[float], new: list[float]) -> list[float]:
    if not old:
        return new
    if not new:
        return old
    return [min(old[0], new[0]), max(old[1], new[1])]

def merge_levels(old_list: list[list[float]], new_list: list[list[float]]) -> list[list[float]]:
    return [merge_ranges(old, new) for old, new in zip(old_list, new_list)]

def seed_weights(
  species_key: str,
  groups: list,
  data: bytearray,
  seed: int,
  seed_unit: int,
  min_score: float,
  gender: int,  # 1=male, 2=female
) -> None:
  # seed animals with incrementing weights to determine level brackets
  # use minimum score to isolate weight as a variable
  eligible_animals: list[AdfAnimal] = []
  for group in groups:
    animals = group.value["Animals"].value
    for animal in animals:
      animal = AdfAnimal(animal, species_key)
      eligible_animals.append(animal)
  if gender not in [1,2]:
    raise ValueError(f"Gender must be 1 (male) or 2 (female) when seeding animals")
  for animal in eligible_animals:
    utils.update_float(data, animal.weight_offset, seed / seed_unit)
    utils.update_float(data, animal.score_offset, min_score)
    utils.update_uint(data, animal.visual_seed_offset, seed)
    utils.update_uint(data, animal.gender_offset, gender)
    utils.update_uint(data, animal.great_one_offset, 0)
    seed += 1
  return seed

def process_aps_levels(species_key: str, filename: Path, attribute: str) -> dict:
  levels = [[] for _ in range(9)]
  with filename.open() as csvfile:
    animals = csvfile.readlines()
    for animal in animals:
      try:
        aps_animal = ApsAnimal(animal)
        if aps_animal.species_key.lower() == species_key.lower():
          level = config.get_difficulty(aps_animal.difficulty)
          i = level - 1
          value = round(getattr(aps_animal, attribute), 3)  # attribute should be "weight" or "score"
          if not levels[i]:
            # print(f"{level} - {animal.difficulty} : {value}")
            levels[i] = [value, value]
          if value < levels[i][0]:
            levels[i][0] = value
          if value > levels[i][1]:
            levels[i][1] = value
      except:
        pass
  return levels

def sanitize_levels(levels: list[list], min_value: float, max_value: float) -> list[list]:
  for i in range(len(levels)):
    if not levels[i]:
      continue
    low, high = levels[i][0], levels[i][1]
    if low > max_value:
      logger.info(f"[yellow]Level {i + 1} low value {low} greater than maximum value {max_value}. Deleting level...[/yellow]")
      levels[i] = []
      continue
    if high < min_value:
      logger.info(f"[yellow]Level {i + 1} high value {high} less than minimum value {min_value}. Deleting level...[/yellow]")
      levels[i] = []
      continue
    if low < min_value:
      logger.info(f"[yellow]Level {i + 1} low value {low} less than minimum value {min_value}. Updating value...[/yellow]")
      levels[i][0] = min_value
    if high > max_value:
      logger.info(f"[yellow]Level {i + 1} high value {high} greater than maximum value {max_value}. Updating value...[/yellow]")
      levels[i][1] = max_value
  try:
    levels[0][0] = min_value
    levels[-1][1] = max_value
  except IndexError:
    pass
  return levels

def parse_level_details(levels: dict) -> dict:
  parsed_levels = [None] * 10
  for level, weights in levels.items():
    parsed_levels[config.get_difficulty_index(level)] = weights
  parsed_levels = [l for l in parsed_levels if l is not None]
  return parsed_levels

def analyze_reserve(path: Path) -> None:
  match = re.search(r'animal_population_(\d{1,2})$', str(path))
  if match:
    reserve_index = int(match.group(1))
  else:
    raise ValueError(f"Unable to parse reserve index: {path}")
  reserve_species = parse_reserve_species(reserve_index)
  (reserve_key, reserve_details) = next(((key, details) for key, details in config.RESERVES.items() if details["index"] == reserve_index), ("unknown", {}))
  known_species = reserve_details.get("species", [])
  pops = populations._get_populations(adf.load_adf(path, txt=True).adf)
  logger.info(f"Index: {reserve_index}   Reserve Key: {reserve_key}   Known Species: {len(known_species)}   Populations: {len(pops)}")
  groups_data = {}
  for pop_i, pop in enumerate(pops):
    species_key = known_species[pop_i] if len(known_species) == len(pops) and known_species[pop_i] != "unknown" else pop_i
    groups = pop.value["Groups"].value
    low_score = 1_000_000
    high_score = 0
    low_weight = 1_000_000
    high_weight = 0
    great_one = False
    for group in groups:
      animals = group.value["Animals"].value
      for animal in animals:
        a = populations.AdfAnimal(animal, "unknown", reserve_key=reserve_key)
        low_score = min(low_score, a.score)
        high_score = max(high_score, a.score)
        low_weight = min(low_weight, a.weight)
        high_weight = max(high_weight, a.weight)
    groups_data[species_key] = {
      "low_score": low_score,
      "high_score": high_score,
      "low_weight": low_weight,
      "high_weight": high_weight,
    }
  print(json.dumps(groups_data, indent=2))

def parse_reserve_species(reserve_index):
  animal_details = config.load_json(ANIMAL_DETAILS_FILE)
  try:
    reserve_data = open_rtpc(config.CONFIG_PATH / f"reserve_{reserve_index}.bin")
  except:
    logger.critical("Unable to locate 'reserve_%d.bin'  in path %s", reserve_index, config.CONFIG_PATH)
    return []
  reserve = RtpcReserve(reserve_index, reserve_data)
  print(reserve.species_ids)
  id_to_name = {data["species_id"]: species_key for species_key, data in animal_details.items()}
  reserve_species = [id_to_name.get(species_id, species_id) for species_id in reserve.species_ids]
  print(reserve_species)
  return reserve_species

def export_reserve_animals_stats(reserve_key: str, species_key: str = None) -> csv:
  loaded_reserve = LoadedReserve(reserve_key, parse=True)
  species_keys = [species_key] if species_key else config.get_reserve_species(reserve_key)
  for species_key in species_keys:
    species_description_full = populations.describe_animals(reserve_key, species_key, loaded_reserve.parsed_adf.adf, precision=4)
    filename = f"{reserve_key}-{species_key}.csv"
    headers = ["gender", "weight", "score"]
    extract_fn=lambda row: [row[2], row[3], row[4]]
    with open(filename, "w", newline='') as f:
      writer = csv.writer(f)
      writer.writerow(headers)
      for animal_data in species_description_full:
        writer.writerow(extract_fn(animal_data))

def show_mouse() -> None:
  try:
      while True:
          x, y = pyautogui.position()
          positionStr = 'X: ' + str(x).rjust(4) + ' Y: ' + str(y).rjust(4)
          logger.debug(positionStr, end='')
          logger.debug('\b' * len(positionStr), end='', flush=True)
  except KeyboardInterrupt:
      logger.debug('\n')

def click() -> None:
  pyautogui.mouseDown()
  time.sleep(0.2)
  pyautogui.mouseUp()

def doubleClick() -> None:
  pyautogui.mouseDown()
  pyautogui.mouseUp()
  pyautogui.mouseDown()
  pyautogui.mouseUp()

def reserve_coords(line: float) -> int:
  x_pos = 200
  y_pos_base = 179
  line_pixels = 17
  y_pos = y_pos_base + (line_pixels * line)
  return (x_pos, y_pos)

def click_reserve(reserve_name: str, no_exit: bool = False) -> None:
  # Select Population File window should be 525x260
  action_duration = 0.5
  dropdown = (450, 175)
  scrollbar_top = (450, 195)
  scrollbar_middle = (450, 260)
  scrollbar_bottom = (450, 325)
  pop_file = (200, 270)
  exit_x = (1600, 115)

  pyautogui.moveTo(dropdown, duration=action_duration)
  click()
  if reserve_name == "hirsch":
    line = 1
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "layton":
    line = 2
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "medved":
    line = 3
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "vurhonga":
    line = 4
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "parque":
    line = 5
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "yukon":
    line = 6
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "cuatro":
    line = 7
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "silver":
    line = 8
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_top, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "teawaroa":
    line = 1
    pyautogui.moveTo(scrollbar_top)
    pyautogui.dragTo(scrollbar_middle, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "rancho":
    line = 0.25
    pyautogui.moveTo(scrollbar_bottom)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "mississippi":
    line = 1.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "revontuli":
    line = 2.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "newengland":
    line = 3.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "emerald":
    line = 4.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "sundarpatan":
    line = 5.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "salzwiesen":
    line = 6.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "alberta":
    line = 7.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()
  if reserve_name == "scotland":
    line = 8.25
    pyautogui.moveTo(scrollbar_middle)
    pyautogui.dragTo(scrollbar_bottom, duration=action_duration)
    pyautogui.moveTo(reserve_coords(line), duration=action_duration)
    click()

  pyautogui.moveTo(pop_file)
  doubleClick()
  if not no_exit:
    close_reserve()

def close_reserve() -> None:
  action_duration = 0.5
  exit_x = (1600, 115)
  pyautogui.moveTo(exit_x, duration=action_duration)
  click()

class ApsAnimal:
  def __init__(self, animal_line: str) -> None:
    animal_parts = animal_line.split(",")
    self.species_key = utils.unformat_key(animal_parts[0])
    self.difficulty = animal_parts[1]
    self.gender = "male" if animal_parts[2].lower() == "male" else "female"
    self.weight = float(animal_parts[3].split(" ")[0])
    self.score = float(animal_parts[4].split(" ")[0])
    self.fur = animal_parts[5].lower().rstrip()

  def __repr__(self) -> str:
    return f"{self.species_key}, {self.difficulty}, {self.gender}, {self.weight}, {self.score}, {self.fur}"

def reset_ini() -> None:
  filename = Path("imgui.ini")
  content = filename.read_text()
  new_content = re.sub(r"Pos=\d+,\d+", "Pos=0,0", content, flags=re.RegexFlag.MULTILINE)
  new_content = re.sub(r"LastPopFile=.*", "LastPopFile=", new_content)
  filename.write_text(new_content)

def launch_aps() -> None:
  reset_ini()
  subprocess.Popen(f"AnimalPopulationScanner.exe -p > scans/scan.csv", shell=True)

def map_aps(reserve_name: str, species_key: str) -> str:
  # APC uses species keys from the `global_animal_data.bin` file
  # APS has some mismatches with unique species keys
  aps_key = {
    "american_alligator": "am._alligator",
    "antelope_jackrabbit": "ant._jackrabbit",
    "cinnamon_teal": "cin_teal",
    "collared_peccary": "coll._peccary",
    "eastern_cottontail_rabbit": "ect_rabbit",
    "eastern_grey_kangaroo": "eg_kangaroo",
    "eastern_wild_turkey": "ew_turkey",
    "eu_bison": "euro_bison",
    "eu_hare": "european_hare",
    "eu_rabbit": "euro_rabbit",
    "eurasian_brown_bear": "brown_bear",
    "eurasian_pine_marten": "pine_marten",
    "eurasian_teal": "eu.teal",
    "eurasian_wigeon": "eu.wigeon",
    "eurasian_woodcock": "woodcock",
    "european_badger": "euro_badger",
    "green_wing_teal": "green-winged_teal",
    "gray_wolf": "grey_wolf",
    "harlequin_duck": "h_duck",
    "north_american_beaver": "beaver",
    "northern_bobwhite_quail": "bobwhite_quail",
    "northern_pintail": "pintail",
    "northern_red_muntjac": "muntjac",
    "prong_horn": "pronghorn",
    "rio_grande_turkey": "rg_turkey",
    "rockymountain_elk": "rm_elk",
    "saltwater_crocodile": "sw_crocodile",
    "siberian_musk_deer": "musk_deer",
    "sidestriped_jackal": "s-striped_jackal",
    "southeastern_ibex": "ses_ibex",
    "tundra_bean_goose": "t.bean_goose",
    "western_capercaillie": "w.capercaillie",
    "wild_turkey": "turkey",
    "woodland_caribou": "caribou",
  }
  # Some animals are duplicated across reserves with unique names
  if reserve_name == "mississippi" and species_key == "feral_pig":
    return "wild_hog"
  # if reserve_name == "silver" and species_key == "puma":
  #   return "mountain_lion"
  return aps_key.get(species_key, species_key)

if __name__ == "__main__":
  update_global_animal_data()
  # parse_reserve_species(20)
  # analyze_reserve(config.get_save_path() / "animal_population_20")
  # Run APS and select "/apc/mods" folder before you can seed animals
  seed_reserve_animal_details("scotland", skip_update_fur=True, skip_levels=False)
  seed_all_reserves()
