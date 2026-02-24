import os
import re
import shutil
import subprocess
import textwrap
import time
import traceback
import webbrowser
from importlib.metadata import version
from pathlib import Path
from typing import Callable

import FreeSimpleGUI as sg
import requests
from packaging.version import Version as package_version

from apc import adf, config, populations, utils
from apc.config import BACKUP_DIR_PATH, MOD_DIR_PATH, Strategy
from apc.logging_config import get_logger
from apcgui import logo

logger = get_logger(__name__)
__version__ = version("apc-revived")

DEFAULT_FONT = "_ 14"
MEDIUM_FONT = "_ 13"
BUTTON_FONT = "_ 13"
SMALL_FONT = "_ 11"
window = None
MESSAGE_DELAY = 0.5
VIEW_MODDED = f"({config.VIEWING_MODDED})"
VIEW_MOD_LOADED = f"({config.VIEWING_LOADED_MOD})"

RESERVE_COLUMNS = None
SPECIES_COLUMNS = None

symbol_closed = "►"
symbol_open = "▼"

class AnimalDetails:
  def __init__(self, species_key: str, gender: str, weight: float, score: float, fur: str, great_one: bool) -> None:
    self.species_key = species_key
    self.gender = gender
    self.gender_key = "male" if gender == config.MALE else "female"
    self.weight = weight
    self.score = score
    self.great_one = great_one
    self.great_one_gender = config.get_great_one_gender(species_key)
    self.fur_name = fur if fur != "" else None
    self._get_fur_key()
    self.diamond_gender = config.get_diamond_gender(species_key)
    self.can_be_diamond = self.gender_key == self.diamond_gender or self.diamond_gender == "both"

  def _get_fur_key(self):
    species_furs = config.get_species_fur_names(self.species_key, self.gender_key, self.great_one)
    logger.debug([f"{i} :: {name} >> {key}" for i, (name, key) in enumerate(zip(species_furs["names"], species_furs["keys"]))])
    if self.fur_name not in species_furs["names"]:
      self.fur_key = None
      return
    fur_index = species_furs["names"].index(self.fur_name)
    self.fur_key = species_furs["keys"][fur_index]
    logger.debug(f"Name: {self.fur_name}   Index: {fur_index}   Key: {self.fur_key}")

  def __repr__(self) -> str:
    return f"{self.gender_key}, {self.weight}, {self.score}, {self.fur}, {self.great_one}"

class MainWindow:
  window: sg.Window

  def __init__(self):
    self.window = self._create_window()

def _check_for_update() -> None:
  release_data = _get_latest_release()
  if release_data:
    latest_tag = release_data.get("tag_name", "").lstrip("v")
    if package_version(latest_tag) > package_version(__version__):
      _show_update_popup(release_data)

def _get_latest_release() -> dict:
  try:
    resp = requests.get("https://api.github.com/repos/RyMaxim/apc/releases/latest", timeout=2)
    resp.raise_for_status()
    data = resp.json()
    return data
  except Exception as e:
    logger.info(f"Check for update failed: {e}")
  return {}

def _show_update_popup(release_data: dict) -> None:
  nexus_url = "https://www.nexusmods.com/thehuntercallofthewild/mods/440?tab=files"
  github_url = release_data["html_url"]
  layout = [
    [sg.Text(f"A newer version is available!", text_color="yellow")],
    [sg.Text(release_data["name"])],
    [sg.Button("NexusMods", key="-NEXUSMODS-"), sg.Button("GitHub", key="-GITHUB-")],
  ]

  window = sg.Window("Update Available", layout, icon=logo.value, modal=True)
  while True:
    event, _ = window.read()
    if event in (sg.WINDOW_CLOSED, "Close"):
      break
    elif event == "-NEXUSMODS-":
      webbrowser.open(nexus_url)
      break
    elif event == "-GITHUB-":
      webbrowser.open(github_url)
      break
  window.close()

def _progress(value: float) -> None:
  global window
  window["progress"].update(value, max=100)
  window.refresh()

def _show_error_window(error):
  layout = [
    [sg.T(f"{config.NEW_BUG}:")],
    [sg.Multiline("https://www.nexusmods.com/thehuntercallofthewild/mods/440?tab=bugs", expand_x=True, no_scrollbar=True, disabled=True)],
    [sg.T(f"{config.ERROR}:")],
    [sg.Multiline(error, expand_x=True, expand_y=True, disabled=True)]
  ]
  window = sg.Window(config.UNEXPECTED_ERROR, layout, modal=True, size=(600, 300), icon=logo.value)
  while True:
    event, _values = window.read()
    if event == sg.WIN_CLOSED:
      break

def _show_popup(message: str, title: str, ok: str, cancel: str = None, checkbox: str = None) -> str:
  buttons = [sg.Button(ok, k="ok", font=DEFAULT_FONT)]
  if cancel:
    buttons.append(sg.Button(cancel, k="cancel", font=DEFAULT_FONT))

  layout = [
    [sg.T(message, font=DEFAULT_FONT, p=(0,10))],
    [sg.Checkbox(checkbox, k="checkbox", font=DEFAULT_FONT)] if checkbox else [],
    [sg.Push(), buttons]
  ]
  window = sg.Window(title, layout, modal=True, icon=logo.value)
  response = None
  while True:
    event, values = window.read()
    if event == "ok":
      if checkbox:
        response = values["checkbox"]
      else:
        response = "ok"
      break
    elif event == sg.WIN_CLOSED or event == "cancel":
      response = "cancel"
      break
  window.close()
  return response

def _show_load_mod_popup(loaded_reserve):
  popup_title = f"{config.UPDATE_ANIMALS}: {loaded_reserve.reserve_name}"
  popup_message = f"{config.UPDATED_ANIMALS_ON_RESERVE}: {loaded_reserve.reserve_name}  [{loaded_reserve.popfilename}]"
  popup_message += f"\n\n {config.CLICK} '{config.FILES}' > '{config.LIST_MODS}' > '{config.LOAD_MOD}' {config.UPDATED_ANIMALS_ON_RESERVE_2}"
  result = _show_popup(popup_message, popup_title, config.OK, checkbox=config.DONT_REMIND_ME)
  return result

def _show_popup_message(message: str, delay: bool = True) -> str:
  sg.PopupQuickMessage(message, font="_ 28", background_color="brown")
  if delay:
    time.sleep(MESSAGE_DELAY)

def _show_export_popup(reserve: str, file: Path) -> str:
  default_path = config.EXPORTS_PATH / file
  layout = [
    [sg.T(f"{config.EXPORT_MSG}:", font=DEFAULT_FONT, p=(0,10))],
    [sg.FileSaveAs(f"{config.EXPORT_AS}...", initial_folder=config.EXPORTS_PATH, font=DEFAULT_FONT, target="export_path", k="export_btn", enable_events=True, change_submits=True), sg.T(default_path, k="export_path")],
    [sg.Push(), sg.Button(config.CANCEL, k="cancel", font=DEFAULT_FONT), sg.Button(config.EXPORT, k="export", font=DEFAULT_FONT)]
  ]
  window = sg.Window(f"{config.EXPORT_MOD}: {reserve}", layout, modal=True, icon=logo.value)
  response = None
  while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
      response = "cancel"
      break
    if event == "export":
      response = values["export_btn"] if values["export_btn"] != '' else default_path
      break
    elif event == "cancel":
      response = "cancel"
      break
  window.close()
  return response

def _show_import_popup(reserve: str, file: str) -> str:
  layout = [
    [sg.T(f"{config.IMPORT_MSG}:", font=DEFAULT_FONT, p=(0,10))],
    [sg.FileBrowse(config.SELECT_FILE, initial_folder=config.EXPORTS_PATH, font=DEFAULT_FONT, target="import_path", k="import_btn"), sg.T(file, k="import_path")],
    [sg.Push(), sg.Button(config.CANCEL, k="cancel", font=DEFAULT_FONT), sg.Button(config.IMPORT, k="import", font=DEFAULT_FONT)]
  ]
  window = sg.Window(f"{config.IMPORT_MOD}: {reserve}", layout, modal=True, icon=logo.value)
  response = None
  while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
      response = "cancel"
      break
    if event == "import":
      response = values["import_btn"]
      break
    elif event == "cancel":
      response = "cancel"
      break
  window.close()
  return response

def _highlight_values(data: list) -> list:
  diamond_index = 6
  great_one_index = 7
  for row in data:
    if row[diamond_index] > 0:
      row[diamond_index] = f"* {row[diamond_index]}"
    else:
      row[diamond_index] = str(row[diamond_index])
    if row[great_one_index] > 0:
      row[great_one_index] = f"** {row[great_one_index]}"
    else:
      row[great_one_index] = str(row[great_one_index])
  return data

def _disable_diamonds(window: sg.Window, disabled: bool) -> None:
  window["diamond_value"].update(disabled = disabled)
  window["gender_value"].update(disabled = disabled)
  window["diamond_party_percent"].update(value=0)
  window.refresh()

def _disable_furs(window: sg.Window, disabled: bool) -> None:
  window["fur_update_animals"].update(disabled = disabled)
  window["fur_party_percent"].update(value=0)
  window["rare_fur_party_percent"].update(value=0)
  window.refresh()

def _disable_great_one(window: sg.Window, disabled: bool) -> None:
  window["great_one_value"].update(disabled = disabled)
  window["great_one_party_percent"].update(value=0)
  window.refresh()

def _disable_new_reserve(window: sg.Window) -> None:
  _disable_diamonds(window, True)
  _disable_furs(window, True)
  _disable_great_one(window, True)
  window["show_animals"].update(disabled=True)
  window["update_animals"].update(disabled=True)

def _disable_animal_details(window: sg.Window, disabled: bool) -> None:
  window["animal_great_one"].update(disabled=disabled)
  window["animal_gender"].update(disabled=disabled)
  window["animal_fur"].update(disabled=disabled)
  window["details_update_animals"].update(disabled=disabled)

def _disable_great_one_parties(window: sg.Window, reserve_key: str) -> None:
  great_one_species = len(config.get_great_one_species(reserve_key)) > 0
  window["great_one_party"].update(disabled=(not great_one_species))
  window["great_one_party_percent"].update(value=0)

def _load_reserve_description(window: sg.Window, values: dict, reserve_key: str, force_reload: bool = True) -> adf.LoadedReserve:
  _progress(0)
  is_modded = values["load_modded"]
  window["modded_reserves"].update(is_modded)
  if is_modded:
    window["modded_label"].update(VIEW_MODDED)
  else:
    window["modded_label"].update(VIEW_MOD_LOADED if _is_reserve_mod_loaded(reserve_key, window) else "")

  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  should_load = (
    loaded_reserve is None
    or loaded_reserve.reserve_key != reserve_key
    or loaded_reserve.modded != is_modded
    or force_reload
  )
  if should_load:
    try:
      loaded_reserve = _load_reserve(window, reserve_key, is_modded=is_modded, show_progress=True)
    except Exception as ex:
      _show_error(ex, delay=False)
      _reset_reserve_description(window)
      loaded_reserve = None
    if loaded_reserve is not None:
      _disable_great_one_parties(window, reserve_key)
      window["diamond_party"].update(disabled=False)
      # window["everyone_party"].update(disabled=False)
      window["fur_party"].update(disabled=False)
      window["rare_fur_party"].update(disabled=False)
      window["reserve_description"].update(_highlight_values(
          _format_reserve_description(loaded_reserve.population_description)
      ))
      all_species_counts = _parse_all_species_counts(loaded_reserve)
      total_animals = sum([count["total"] for count in all_species_counts.values()])
      window["total_animals"].update(total_animals)
      _progress(100)
      _show_message(f"{config.ANIMALS_LOADED}{f' ({config.MODDED})' if loaded_reserve.modded else ''}: {reserve_key}")
      _show_message("", delay=False)
      _progress(0)
    else:
      _reset_reserve_description(window)
  window["reserve"].metadata = loaded_reserve

def _load_reserve(window: sg.Window, reserve_key: str, is_modded: bool = False, show_progress: bool = False) -> adf.LoadedReserve:
  if show_progress:
    _progress(0)
    _clear_message()
  try:
    loaded_reserve = adf.LoadedReserve(reserve_key, is_modded)
    modded_text = f" ({config.MODDED})" if is_modded else ""
    if show_progress:
      _show_message(f"{config.LOADING_ANIMALS}{modded_text}: {loaded_reserve.reserve_key}  [{loaded_reserve.filename}]")
      _progress(50)
    loaded_reserve.parse()
    if show_progress:
      _progress(75)
  except adf.FileNotFound as ex:
    _show_error(ex, delay=False)
    if str(ex).startswith(config.FILE_NOT_FOUND):
      error_title = f"{config.FILE_NOT_FOUND}: {config.get_population_file_name(reserve_key)}"
      error_message = f"{config.MAP_DATA_NOT_FOUND}: {config.get_reserve_name(reserve_key)} [{config.get_population_file_name(reserve_key)}]\n\n{config.MAP_DATA_NOT_FOUND_INSTRUCTIONS}"
      _show_popup(error_message, error_title, config.OK)
    else:
      _show_popup_message(ex)
    return None
  loaded_reserve.population_description, loaded_reserve.species_groups = populations.describe_reserve(reserve_key, loaded_reserve.parsed_adf.adf)
  # loaded_reserve.describe_reserve()
  all_species_counts = _parse_all_species_counts(loaded_reserve)
  total_animals = sum([count["total"] for count in all_species_counts.values()])
  logger.debug(f"{reserve_key} total animals: {total_animals}")
  logger.debug(f"{reserve_key} total size: {loaded_reserve.parsed_adf.decompressed.org_size}")
  if show_progress:
    _progress(90)
  return loaded_reserve

def _show_species_description(window: sg.Window, reserve_key: str, species_key: str, is_modded: bool, is_top: bool) -> None:
  is_loaded_mod = _is_reserve_mod_loaded(reserve_key, window)
  window["reserve_description"].update(visible=False)
  window["modding"].update(visible=False)
  window["species_description"].update(visible=True)
  window["show_reserve"].update(visible=True)
  window["exploring"].update(visible=True)
  window["exploring"].metadata = (-1, True)
  species_text = [config.get_species_name(species_key)]
  is_modded and species_text.append(f"({config.MODDED})")
  is_loaded_mod and species_text.append(f"({config.LOADED_MOD})")
  is_top and species_text.append(f"({config.TOP_10})")
  window["species_name"].update(" ".join(species_text))
  window["mod_list"].update(visible=False)

def _show_reserve_description(window: sg.Window, values: dict, reserve_key: str) -> None:
    window["reserve_description"].update(visible=True)
    window["modding"].update(visible=True)
    window["species_description"].update(visible=False)
    window["show_reserve"].update(visible=False)
    window["exploring"].update(visible=False)
    window["exploring"].metadata = (-1, True)
    window["species_name"].update("")
    window["species_name"].metadata = ""
    window["modded_label"].update(visible=True)
    window["mod_list"].update(visible=False)
    window["mod_tab"].update(disabled=False)
    window["mod_tab"].select()
    window["fur_tab"].update(disabled=False)
    window["explore_tab"].update(disabled=False)
    window["party_tab"].update(disabled=False)
    window["load_mod"].update(disabled=True)
    window["unload_mod"].update(disabled=True)
    window["export_mod"].update(disabled=True)
    window["import_mod"].update(disabled=True)
    _reset_mod(window)
    _reset_furs(window)
    _reset_parties(window)
    _disable_great_one_parties(window, reserve_key)
    _clear_animal_details(window)
    _disable_animal_details(window, True)

def _show_mod_list(window: sg.Window) -> None:
  window["reserve_description"].update(visible=False)
  window["mod_list"].update(visible=True)
  window["show_reserve"].update(visible=True)
  window["mod_tab"].update(disabled=True)
  window["fur_tab"].update(disabled=True)
  window["explore_tab"].update(disabled=True)
  window["party_tab"].update(disabled=True)
  window["load_mod"].update(disabled=True)
  window["unload_mod"].update(disabled=True)
  window["export_mod"].update(disabled=True)
  window["import_mod"].update(disabled=True)


def _animal_selected(window: sg.Window, values: dict, row: int) -> None:
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  window["update_animals"].update(disabled=False)
  # species_name = loaded_reserve.population_description[row][2] if loaded_reserve.population_description else ""
  # species_key = loaded_reserve.population_description[row][0] if loaded_reserve.population_description else ""
  # window["species_name"].metadata = loaded_reserve.population_description[row][0] if loaded_reserve.population_description else ""
  # species_key = window["species_name"].metadata
  window["reserve_description"].metadata = loaded_reserve.population_description[row]
  window["species_name"].metadata = window["reserve_description"].metadata[0]
  species_key = window["species_name"].metadata
  _clear_message()
  _disable_great_one(window, True)
  _disable_furs(window, True)
  _disable_diamonds(window, False)
  window["show_animals"].update(disabled=False)
  if config.valid_great_one_species(species_key):
    _disable_great_one(window, False)
  if config.valid_fur_species(species_key):
    _disable_furs(window, False)

  if not (species_counts := _parse_species_counts(window, values)):
    return
  _update_mod_animal_counts(window, values, species_counts)

  male_furs = config.get_species_fur_names(species_key, "male", great_one=False)
  female_furs = config.get_species_fur_names(species_key, "female", great_one=False)
  window["male_furs"].update(values=male_furs["names"])
  window["male_furs"].metadata = male_furs
  window["female_furs"].update(values=female_furs["names"])
  window["female_furs"].metadata = female_furs
  window["male_fur_animals_cnt"].update(value = 0, range=(0, species_counts["male"] - species_counts["great_one"]))
  window["female_fur_animals_cnt"].update(value = 0, range=(0, species_counts["female"]))
  window["male_all_furs"].update(False)
  window["female_all_furs"].update(False)
  diamond_gender = config.get_diamond_gender(species_key)
  if diamond_gender == "male":
    window["diamond_furs"].update(values=male_furs["names"])
    window["diamond_gender"].update(f"({config.MALES.lower()})")
  elif diamond_gender == "female":
    window["diamond_furs"].update(values=female_furs["names"])
    window["diamond_gender"].update(f"({config.FEMALES.lower()})")
  elif diamond_gender == "both":
    male_labeled = [f"{x} ({config.MALE.lower()})" for x in male_furs["names"]]
    female_labeled = [f"{x} ({config.FEMALE.lower()})" for x in female_furs["names"]]
    window["diamond_furs"].update(values=male_labeled+female_labeled)
    window["diamond_gender"].update(f"({config.MALES.lower()} and {config.FEMALES.lower()})")
  else:
    window["diamond_furs"].update([])
    window["diamond_gedner"].update("")
  window.refresh()

def _viewing_modded(window: sg.Window) -> bool:
  return window["modded_label"].get() == VIEW_MODDED

def _is_diamond_enabled(window: sg.Window, value: int) -> bool:
  return value != 0

def _is_great_one_enabled(window: sg.Window, value: int) -> bool:
  return not window["great_one_value"].Disabled and value != 0

def _show_error(ex: Exception, delay: bool = True) -> None:
  global window
  _progress(0)
  window["message_box"].update(f"{config.ERROR}: {ex}")
  window.refresh()
  logger.error("ERROR", exc_info=True)
  if delay:
    time.sleep(2)

def _show_warning(message: str) -> None:
  global window
  _progress(0)
  window["message_box"].update(f"{config.WARNING}: {message}")
  window.refresh()
  time.sleep(1)

def _show_message(message: str, delay: bool = False) -> None:
  global window
  window["message_box"].update(message)
  window.refresh()
  if delay:
    time.sleep(MESSAGE_DELAY)

def _clear_message() -> None:
  _show_message("", delay=False)

def _clear_furs(window: sg.Window) -> None:
  window["male_furs"].update([])
  window["female_furs"].update([])
  window["diamond_furs"].update(values=[])
  window["diamond_gender"].update("")

def _mod_furs(window: sg.Window, male_fur_keys: list[str], female_fur_keys: list[str], male_fur_cnt: int, female_fur_cnt: int):
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  species_key = window["species_name"].metadata
  logger.debug(f'Modding Furs: {loaded_reserve.reserve_key} - {species_key} - "furs" - {male_fur_keys} - {male_fur_cnt} - {female_fur_keys} - {female_fur_cnt}')
  _progress(25)
  try:
    populations.mod_furs(loaded_reserve, species_key, male_fur_keys, female_fur_keys, male_fur_cnt, female_fur_cnt, progress_bar=window["progress"], message_box=window["message_box"])
    _progress(50)
    loaded_reserve = _load_reserve(window, loaded_reserve.reserve_key, is_modded=True, show_progress=False)
  except Exception as ex:
    _show_error(ex)
    return
  _progress(75)
  window["reserve"].metadata = loaded_reserve
  window["reserve_description"].update(select_rows = [])
  window["load_modded"].update(True)
  window["modded_label"].update(VIEW_MODDED)
  window["fur_update_animals"].update(disabled = True)
  window["show_animals"].update(disabled=True)
  window["update_animals"].update(disabled=True)
  window["modded_reserves"].update(True)
  _progress(100)
  _show_message(f"{config.get_species_name(species_key)} ({config.JUST_FURS}) {config.SAVED}: \"{MOD_DIR_PATH / loaded_reserve.filename}\"")
  if window["load_mod"].metadata != True:
    window["load_mod"].metadata = _show_load_mod_popup(loaded_reserve)
  _progress(0)
  _reset_furs(window)
  _clear_furs(window)

def _mod_diamonds(window: sg.Window, species_key: str, diamond_cnt: int, male_fur_keys: list[str], female_fur_keys: list[str]) -> None:
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  species_key = window["species_name"].metadata
  logger.info(f'Modding Diamonds: {loaded_reserve.reserve_key} - {species_key} "diamonds" - {diamond_cnt} - {male_fur_keys} - {female_fur_keys}')
  _progress(25)
  try:
    populations.mod_diamonds(loaded_reserve, species_key, diamond_cnt, male_fur_keys, female_fur_keys, progress_bar=window["progress"], message_box=window["message_box"])
    _progress(50)
    loaded_reserve = _load_reserve(window, loaded_reserve.reserve_key, is_modded=True, show_progress=False)
  except Exception as ex:
    _show_error(ex)
    return
  _progress(75)
  window["reserve"].metadata = loaded_reserve
  window["reserve_description"].update(_highlight_values(_format_reserve_description(loaded_reserve.population_description)))
  window["modded_label"].update(VIEW_MODDED)
  _progress(100)
  _show_message(f"{config.get_species_name(species_key)} (Diamonds) {config.SAVED}: \"{MOD_DIR_PATH / loaded_reserve.filename}\"")
  if window["load_mod"].metadata != True:
    window["load_mod"].metadata = _show_load_mod_popup(loaded_reserve)
  _progress(0)
  window["show_animals"].update(disabled=True)
  window["update_animals"].update(disabled=True)
  window["modded_reserves"].update(True)
  window["fur_update_animals"].update(disabled = True)

def _mod_animals(window: sg.Window, values: dict, species_key: str, animal_details: AnimalDetails, adf_animals: list[adf.AdfAnimal]) -> None:
  selected_reserve_keys = list({a.reserve_key for a in adf_animals})
  logger.debug(selected_reserve_keys)
  count = 0
  _progress(0)
  for reserve_key in selected_reserve_keys:
    reserve_animals = [adf_animal for adf_animal in adf_animals if adf_animal.reserve_key == reserve_key]
    count = _mod_reserve_animals(window, values, reserve_key, species_key, animal_details, reserve_animals, count, len(adf_animals))
  window["load_modded"].update(value=True)
  window["modded_reserves"].update(value=True)
  window["modded_label"].update(VIEW_MODDED)
  _progress(100)
  _show_message(f"{config.UPDATE_ANIMALS}: {len(adf_animals)}/{len(adf_animals)}")
  _progress(0)
  if len(selected_reserve_keys) > 1:
    popup_message = f"{config.UPDATED_MULTIPLE_RESERVES} {config.FILES} > {config.LIST_MODS} > {config.LOAD_MOD} {config.UPDATED_MULTIPLE_RESERVES_2}\n"
    for reserve_key in selected_reserve_keys:
      popup_message += f"\n - {config.get_reserve_name(reserve_key)}  [{config.get_population_file_name(reserve_key)}]"
    popup_title = f"{config.UPDATE_ANIMALS}: {len(selected_reserve_keys)} {config.RESERVES_TITLE}"
    _show_popup(popup_message, popup_title, config.OK)#, config.CANCEL)
  _clear_animal_details(window)
  _disable_animal_details(window, True)
  window["species_description"].update(select_rows=[])
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  if loaded_reserve.reserve_key in selected_reserve_keys:
    try:
      window["reserve"].metadata = _load_reserve(window, loaded_reserve.reserve_key, is_modded=True, show_progress=False)
    except Exception as ex:
      _show_error(ex)

def _mod_reserve_animals(window: sg.Window, values: dict, reserve_key: str, species_key: str, animal_details: AnimalDetails, adf_animals: list[adf.AdfAnimal], count: int, total: int) -> int:
  progress_per_animal = 100/total
  is_modded = _viewing_modded(window)
  if (loaded_reserve := _load_reserve(window, reserve_key, is_modded=is_modded, show_progress=False)):
    for adf_animal in adf_animals:
      try:
        weight = animal_details.weight if values["animal_weight_checkbox"] else adf_animal.weight
        score = animal_details.score if values["animal_score_checkbox"] else adf_animal.score
        fur = animal_details.fur_key if values["animal_fur_checkbox"] else adf_animal.visual_seed
        populations.mod_animal(loaded_reserve, adf_animal, animal_details.great_one, animal_details.gender_key, weight, score, fur)
      except Exception as ex:
        _show_error(ex)
      count += 1
      _progress(progress_per_animal * count)
      _show_message(f"{config.UPDATE_ANIMALS}: {count}/{total}", delay=False)
    loaded_reserve.save()
  else:
    count += len(adf_animals)
    _progress(progress_per_animal * count)
    _show_message(f"{config.UPDATE_ANIMALS}: {count}/{total}")
  _show_message(f'{config.get_species_name(species_key)} ({config.UPDATE_ANIMALS}) {config.SAVED}: "{MOD_DIR_PATH / loaded_reserve.filename}"')
  if window["load_mod"].metadata != True:
    window["load_mod"].metadata = _show_load_mod_popup(loaded_reserve)
  return count

def _mod(window: sg.Window, species_key: str, strategy: Strategy, modifier: int, rares: bool = False, percentage: bool = False, party: bool = False) -> None:
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  logger.debug((loaded_reserve.reserve_key, species_key, strategy.value, modifier, rares))
  # _progress(25)
  try:
    populations.mod(loaded_reserve, species_key, strategy.value, rares=rares, modifier=modifier, percentage=percentage, party=party, progress_bar=window["progress"], message_box=window["message_box"])
    # _progress(50)
    loaded_reserve = _load_reserve(window, loaded_reserve.reserve_key, is_modded=True, show_progress=True)
  except Exception as ex:
    _show_error(ex)
    return
  # _progress(75)
  window["reserve"].metadata = loaded_reserve
  window["reserve_description"].update(_highlight_values(_format_reserve_description(loaded_reserve.population_description)))
  window["modded_label"].update(VIEW_MODDED)
  _progress(100)
  _show_message(f"{config.get_species_name(species_key)} ({utils.format_key(strategy)}) {config.SAVED}: \"{MOD_DIR_PATH / loaded_reserve.filename}\"")
  if window["load_mod"].metadata != True:
    window["load_mod"].metadata = _show_load_mod_popup(loaded_reserve)
  _progress(0)
  window["load_modded"].update(value=True)
  window["modded_reserves"].update(value=True)
  window["show_animals"].update(disabled=True)
  window["update_animals"].update(disabled=True)
  window["modded_reserves"].update(True)
  window["fur_update_animals"].update(disabled = True)

def _mod_animal_count(window: sg.Window, species_key: str, animal_count: int, gender: str) -> None:
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  logger.debug(f"{'Adding' if animal_count > 0 else 'Removing'} {abs(animal_count)} {gender} {species_key} {'to' if animal_count > 0 else 'from'} {loaded_reserve.reserve_key}")
  _show_message(f"{'Adding' if animal_count > 0 else 'Removing'} {abs(animal_count)} {config.MALE if gender == "male" else config.FEMALE} {config.get_species_name(species_key)} {'to' if animal_count > 0 else 'from'} {loaded_reserve.reserve_key}")
  _progress(0)
  populations.mod_animal_cnt(loaded_reserve, species_key, animal_count, gender, progress_bar=window["progress"], message_box=window["message_box"])
  loaded_reserve = _load_reserve(window, loaded_reserve.reserve_key, is_modded=True, show_progress=True)
  # except Exception as ex:
    # _show_error(ex)
    # return
  window["reserve"].metadata = loaded_reserve
  window["reserve_description"].update(_highlight_values(_format_reserve_description(loaded_reserve.population_description)))
  window["modded_label"].update(VIEW_MODDED)
  _progress(100)
  _show_message(f"{config.get_species_name(species_key)} ({config.MALE if gender == "male" else config.FEMALE}) {config.SAVED}: \"{MOD_DIR_PATH / loaded_reserve.filename}\"")
  if window["load_mod"].metadata != True:
    window["load_mod"].metadata = _show_load_mod_popup(loaded_reserve)
  _progress(0)
  window["load_modded"].update(value=True)
  window["modded_reserves"].update(value=True)
  window["show_animals"].update(disabled=True)
  window["update_animals"].update(disabled=True)
  window["modded_reserves"].update(True)
  window["fur_update_animals"].update(disabled = True)

def _ensure_enough_party_gender(
  window: sg.Window,
  species_key: str,
  counts: dict,
  target_gender: str,
  party_key: str,
  party_name: str,
  display_name: str,
  animals_to_mod: int
) -> None:
  current_count = counts[party_key]
  if target_gender == "both":
    eligible_count = counts["male"] + counts["female"] - current_count
  else:
    eligible_count = counts[target_gender] - current_count
  if party_key == "diamond":
    eligible_count -= counts["great_one"]
    # animals_to_mod -= counts["great_one"]
  if eligible_count < 0:
    eligible_count = 0
  gender_deficit = max(animals_to_mod - eligible_count, 0)
  logger.debug(f"Current: {current_count}   To mod: {animals_to_mod}   Eligible: {eligible_count}   Deficit: {gender_deficit}")

  if gender_deficit > 0:
    if target_gender == "male":
      strategy_enum = Strategy.males
      gender_text = config.MORE_MALES
    elif target_gender == "female":
      strategy_enum = Strategy.females
      gender_text = config.MORE_FEMALES
    logger.info(
      f"Not enough {target_gender} {species_key} to create {display_name}. "
      f"Converting {gender_deficit} {"females" if target_gender == "male" else "males"} to {target_gender}s"
    )
    _show_message(f"{party_name}! {config.get_species_name(species_key)}: {gender_text} x {gender_deficit}", delay=False)
    try:
      _mod(window, species_key, strategy_enum, gender_deficit, party=True)
    except populations.NoAnimalsException as ex:
      _show_error(ex)

def _run_party(
  window: sg.Window,
  values: dict,
  party_key: str,
  *,
  party_name: str,
  display_name: str,
  more_display_name: str,
  complete_suffix: str,
  gender_func: Callable[[str], str | None],
  strategy_enum: Strategy,
) -> None:
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  if not loaded_reserve:
    _show_message(config.SELECT_A_RESERVE)
    return
  mod_percent = int(values[f"{party_key}_party_percent"])
  if mod_percent <= 0:
    return
  for species_data in loaded_reserve.population_description:
    species_counts = _parse_species_counts(window, values, species_data=species_data)
    species_key = species_counts["species_key"]
    if (gender := gender_func(species_key)) is None:
      continue
    goal_count = int(species_counts["total"] * mod_percent / 100)
    current_count = species_counts[party_key]
    animals_to_mod = goal_count - current_count
    if animals_to_mod <= 0:
      _show_message(f"{party_name}! {config.get_species_name(species_key)}: {more_display_name} x 0")
      continue
    _ensure_enough_party_gender(window, species_key, species_counts, gender, party_key, party_name, display_name, animals_to_mod)
    logger.info(f"Converting {animals_to_mod} {gender} {species_key} to {display_name}s")
    _show_message(f"{party_name}! {config.get_species_name(species_key)}: {more_display_name} x {animals_to_mod}", delay=False)
    try:
      _mod(window, species_key, strategy_enum, animals_to_mod, party=True)
    except populations.NoAnimalsException as ex:
      _show_error(ex)
  _show_message(f"{mod_percent}% {complete_suffix}")
  _disable_new_reserve(window)

def _run_fur_party(window: sg.Window, values: dict, *, percent_key: str, party_label: str, complete_suffix: str, rare: bool = False) -> None:
  loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
  if not loaded_reserve:
    _show_message(config.SELECT_A_RESERVE)
    return
  mod_percent = int(values[percent_key])
  if mod_percent <= 0:
    return
  for species_data in loaded_reserve.population_description:
    counts = _parse_species_counts(window, values, species_data=species_data)
    species_key = counts["species_key"]
    animals_to_mod = int((counts["total"] - counts["great_one"]) * mod_percent / 100)
    if animals_to_mod <= 0:
      _show_message(f"{party_label}! {config.get_species_name(species_key)} x 0")
      continue
    _show_message(f"{party_label}! {config.GENERATE_FUR_SEEDS}: {config.get_species_name(species_key)} x {animals_to_mod}", delay=False)
    _mod(window, species_key, Strategy.furs_some, animals_to_mod, rares=rare)
  _show_message(f"{mod_percent}% {complete_suffix}")

def _list_mods(window: sg.Window) -> list[list[str]]:
  if not MOD_DIR_PATH.exists():
    return _show_warning(f"{MOD_DIR_PATH} {config.DOES_NOT_EXIST}.")

  file_format = re.compile(r"^.*animal_population_\d+$")
  items = os.scandir(MOD_DIR_PATH)
  mods = []
  for item in items:
    item_path = MOD_DIR_PATH / item.name
    if item.is_file() and file_format.match(item.name):
      already_loaded = (BACKUP_DIR_PATH / item.name).exists()
      already_loaded_name = config.YES if already_loaded else "-"
      mods.append([config.get_population_name(item.name), already_loaded_name, item_path, item.name, already_loaded])
  mods.sort(key=lambda x: int(re.search(r'_(\d+)$', x[3]).group(1)))  # sort by "x" in  "animal_population_x"
  return mods

def _is_reserve_mod_loaded(reserve_key: str, window: sg.Window) -> bool:
  mods = _list_mods(window)
  for mod in mods:
    if config.get_population_reserve_key(mod[3]) == reserve_key:
      return mod[4]

def _copy_file(filename: Path, destination: Path) -> None:
  logger.debug(f"copy {filename} to {destination}")
  return shutil.copy2(filename, destination)

def _backup_exists(filename: Path) -> bool:
  return (BACKUP_DIR_PATH / filename.name).exists()

def _load_mod(window: sg.Window, filename: Path) -> None:
  _clear_message()
  try:
    if not _backup_exists(filename):
      game_file = config.get_save_path() / filename.name
      if game_file.exists():
        backup_path = _copy_file(game_file, BACKUP_DIR_PATH)
        if not backup_path:
          _show_warning(f"{config.FAILED_TO_BACKUP} {game_file}")
          return
    else:
      logger.info("backup already exists")
    _progress(50)
    game_path = _copy_file(filename, config.get_save_path())
    if not game_path:
      _show_warning(f"{config.FAILED_TO_LOAD_MOD} {filename}")
      return
    _progress(100)
    sg.PopupQuickMessage(config.MOD_LOADED, font="_ 28", background_color="brown")
    time.sleep(MESSAGE_DELAY)
  except Exception:
    logger.error(traceback.format_exc())
    _show_warning({config.FAILED_TO_LOAD_MOD})
  _progress(0)

def _unload_mod(window: sg.Window, filename: Path) -> None:
  _clear_message()
  try:
    backup_file = BACKUP_DIR_PATH / filename.name
    game_path = config.get_save_path()
    if not backup_file.exists():
      _show_warning(f"{backup_file} {config.DOES_NOT_EXIST}")
      return
    game_path = _copy_file(backup_file, game_path)
    if not game_path:
      _show_warning(f"{config.FAILED_TO_LOAD_BACKUP} {game_path}")
      return
    _progress(50)
    os.remove(backup_file)
    _progress(100)
    sg.PopupQuickMessage(config.MOD_UNLOADED, font="_ 28", background_color="brown")
    time.sleep(MESSAGE_DELAY)
  except Exception:
    logger.error(traceback.format_exc())
    _show_warning(f"{config.FAILED_TO_UNLOAD_MOD}")
  _progress(0)

def _process_list_mods(window: sg.Window, reserve_name: str = None) -> list:
  _clear_message()
  _show_mod_list(window)
  _progress(30)
  mods = _list_mods(window)
  _progress(60)
  window["mod_list"].update(mods)
  if reserve_name:
    for mod_i, mod in enumerate(mods):
      if mod[0] == reserve_name:
        window["mod_list"].update(select_rows=[mod_i])
  _progress(100)
  time.sleep(MESSAGE_DELAY)
  _progress(0)
  return mods

def _format_reserve_description(reserve_description: list[list]) -> list:
  rows = []
  for row in reserve_description:
    rows.append(row[2:])
  return rows

def _reset_reserve_description(window: sg.Window) -> None:
  window["reserve_description"].update([])
  window["total_animals"].update(0)
  window["great_one_party"].update(disabled=True)
  window["diamond_party"].update(disabled=True)
  # window["everyone_party"].update(disabled=True)
  window["fur_party"].update(disabled=True)
  window["rare_fur_party"].update(disabled=True)
  window["show_animals"].update(disabled=True)
  _reset_parties(window)

def _reset_mod(window: sg.Window) -> None:
  window["gender_value"].update(0, range=(0,0), disabled=False)
  window["gender_value"].Widget["troughcolor"] = "#705e52"  # color for our theme: print(tk_slider["troughcolor"])
  window["new_female_value"].update(0)
  window["new_male_value"].update(0)
  window["add_remove_animals"].update(False)
  window["great_one_value"].update(0, range=(0,0))
  window["diamond_value"].update(0, range=(0,0))
  window["diamond_all_furs"].update(False)
  window["diamond_furs"].update(set_to_index=[])
  window["reserve_description"].update(select_rows=[])
  window["species_name"].metadata = ""

def _reset_furs(window: sg.Window) -> None:
  window["male_all_furs"].update(False)
  window["female_all_furs"].update(False)
  window["male_furs"].update(set_to_index=[])
  window["female_furs"].update(set_to_index=[])
  window["male_fur_animals_cnt"].update(0)
  window["female_fur_animals_cnt"].update(0)

def _reset_parties(window: sg.Window) -> None:
  window["great_one_party_percent"].update(value=0)
  window["diamond_party_percent"].update(value=0)
  # window["everyone_party"].update(value=0)
  window["fur_party_percent"].update(value=0)
  window["rare_fur_party_percent"].update(value=0)

def _clear_animal_details(window: sg.Window) -> None:
  window["animal_great_one"].update([])
  window["animal_gender"].update([])
  window["animal_weight"].update(0, range=(0,0))
  window["animal_weight_checkbox"].update(True)
  window["animal_weight_info"].update("")
  window["animal_score"].update(0, range=(0,0))
  window["animal_score_checkbox"].update(True)
  window["animal_score_info"].update("")
  window["animal_fur"].update(values=[])
  window["animal_fur_checkbox"].update(True)

def _update_mod_animal_counts(window: sg.Window, values: dict, species_counts: dict, changing: str = None) -> None:
  species_key = window["species_name"].metadata
  diamond_gender = config.get_diamond_gender(species_key)
  great_one_gender = config.get_great_one_gender(species_key)
  more_great_ones = int(values["great_one_value"])

  if changing not in ["new_female_value", "new_male_value"]:
    female_count = int(species_counts["female"] - values["gender_value"])
    male_count = int(species_counts["male"] + values["gender_value"])
  else:
    try:
      female_count = int(values["new_female_value"])
    except ValueError:
      female_count = 0
    female_count = max(female_count, 0)
    try:
      male_count = int(values["new_male_value"])
    except ValueError:
      male_count = 0
    male_count = max(male_count, 0)

  if changing == "new_female_value":
    if not values["add_remove_animals"]:
      female_count = min(female_count, species_counts["total"])
      male_count = species_counts["total"] - female_count

  if changing == "new_male_value":
    if not values["add_remove_animals"]:
      male_count = min(male_count, species_counts["total"])
      female_count = species_counts["total"] - male_count

  logger.debug(f"F: {female_count}   M: {male_count}")
  window["new_female_value"].update(female_count)
  window["new_male_value"].update(male_count)

  male_pool = male_count
  female_pool = female_count
  total_pool = male_pool + female_pool

  if great_one_gender == "male":
    max_great_ones = max(0, male_count - species_counts["great_one"])
    male_pool -= (species_counts["great_one"] + more_great_ones)
    total_pool -= (species_counts["great_one"] + more_great_ones)
  elif great_one_gender == "female":
    max_great_ones = max(0, female_count - species_counts["great_one"])
    female_pool -= (species_counts["great_one"] + more_great_ones)
    total_pool -= (species_counts["great_one"] + more_great_ones)
  elif great_one_gender == "both":
    # TODO: Support for male+female Great One counts
    max_great_ones = max(0, male_count + female_count - species_counts["great_one"])
    total_pool -= (species_counts["great_one"] + more_great_ones)
  else:
    max_great_ones = 0

  if diamond_gender == "male":
    max_diamonds = max(0, male_pool - species_counts["diamond"])
  elif diamond_gender == "female":
    max_diamonds = max(0, female_pool - species_counts["diamond"])
  else:
    max_diamonds = max(0, total_pool - species_counts["diamond"])

  if changing in (None, "male", "female", "new_male_value", "new_female_value"):
    window["great_one_value"].update(value=0, range=(0, max_great_ones))

  if changing in (None, "male", "female", "new_male_value", "new_female_value", "great_one_value"):
    # TODO: possible bug here if an animal can be both male+female Great One but only one gender Diamond
    window["diamond_value"].update(value=0, range=(0, max_diamonds))

  if changing in (None, "new_male_value", "new_female_value"):
    window["gender_value"].update(value=0, range=(-male_pool, female_pool))

def _sort_species_description(window, col):
  species_description = window["species_description"].Values
  adf_animals: list[adf.AdfAnimal] = window["species_description"].metadata
  prev_col, reverse = window["exploring"].metadata
  reverse = not reverse if prev_col == col else True
  if col == 0:
    logger.debug("Sorting by RESERVE")
    species_description.sort(key=lambda x: x[0], reverse=reverse)
    adf_animals.sort(key=lambda x: config.get_reserve_name(x.reserve_key), reverse=reverse)
  if col in (1,3):
    logger.debug("Sorting by WEIGHT")
    species_description.sort(key=lambda x: x[3], reverse=reverse)
    adf_animals.sort(key=lambda x: x.weight, reverse=reverse)
  if col in (4,6):
    logger.debug("Sorting by SCORE")
    species_description.sort(key=lambda x: x[4], reverse=reverse)
    adf_animals.sort(key=lambda x: x.score, reverse=reverse)
  if col == 2:
    logger.debug("Sorting by GENDER")
    species_description.sort(key=lambda x: x[2], reverse=reverse)
    adf_animals.sort(key=lambda x: x.gender, reverse=reverse)
  if col == 5:
    logger.debug("Sorting by FUR")
    species_description.sort(key=lambda x: x[5], reverse=reverse)
    adf_animals.sort(key=lambda x: x.fur_name, reverse=reverse)
  window["species_description"].update(species_description)
  window["species_description"].metadata = adf_animals
  window["exploring"].metadata = (col, reverse)
  window.refresh()

def _parse_animal_row(animal_description: list, species_key: str) -> AnimalDetails:
  animal_gender = animal_description[2]
  animal_weight = animal_description[3]
  animal_score = animal_description[4]
  animal_fur = animal_description[5] if animal_description[5] != "-" else None
  animal_great_one = animal_description[6] == config.GREATONE
  return AnimalDetails(species_key, animal_gender, animal_weight, animal_score, animal_fur, animal_great_one)

def _parse_animal_details(values: dict, species_key: str) -> AnimalDetails:
  return AnimalDetails(species_key, values["animal_gender"], values["animal_weight"], values["animal_score"], values["animal_fur"], values["animal_great_one"] == config.YES)

def _update_animal_details(window: sg.Window, animal_details: AnimalDetails) -> None:
  species_key = window["species_name"].metadata
  species_config = config.get_species(species_key)
  great_one_species = config.valid_great_one_species(species_key)
  gender_key = animal_details.gender_key

  if animal_details.great_one:
    low_weight = species_config["gender"][f"great_one_{gender_key}"]["weight_low"]
    high_weight = species_config["gender"][f"great_one_{gender_key}"]["weight_high"]
    low_score = species_config["gender"][f"great_one_{gender_key}"]["score_low"]
    high_score = species_config["gender"][f"great_one_{gender_key}"]["score_high"]
    window["animal_gender"].update(animal_details.gender, disabled=True)
  else:
    low_weight = round(species_config["gender"][gender_key]["weight_low"], 1)
    high_weight = round(species_config["gender"][gender_key]["weight_high"], 1)
    low_score =  round(species_config["gender"][gender_key]["score_low"], 1)
    high_score = round(species_config["gender"][gender_key]["score_high"], 1)
    window["animal_gender"].update(animal_details.gender, disabled=False)

    diamond_low_weight = round(species_config["trophy"]["diamond"]["weight_low"], 1)
    diamond_low_score = round(species_config["trophy"]["diamond"]["score_low"], 1)

  if great_one_species:
    window["animal_great_one"].update(disabled=False)
  else:
    window["animal_great_one"].update(config.NO, disabled=True)

  window["animal_great_one"].update(config.YES if animal_details.great_one else config.NO)
  window["animal_weight"].update(value = animal_details.weight, range=(low_weight, high_weight))
  window["animal_score"].update(value = animal_details.score, range=(low_score, high_score))
  if animal_details.can_be_diamond and not animal_details.great_one:
    window["animal_weight_info"].update(f"({config.DIAMOND}: {diamond_low_weight})")
    window["animal_score_info"].update(f"({config.DIAMOND}: {diamond_low_score})")
  else:
    window["animal_weight_info"].update(f"")
    window["animal_score_info"].update(f"")

  species_furs = config.get_species_fur_names(species_key, animal_details.gender_key, great_one=animal_details.great_one)
  window["animal_fur"].update(animal_details.fur_name, values=species_furs["names"])

def _show_animals(
  window: sg.Window,
  values: dict,
  modded: bool = False
) -> tuple[list[list], list[adf.AdfAnimal]]:
  _progress(0)
  loaded_reserve: adf.LoadedReserve
  if not (loaded_reserve := window["reserve"].metadata):
    _show_message(config.SELECT_A_RESERVE)
    return
  if not (species_key := window["species_name"].metadata):
    _show_message(config.SELECT_AN_ANIMAL)
    return
  is_modded = values["modded_reserves"] or modded
  is_top = values["top_scores"]
  window["modded_label"].update(visible=False)
  # _progress(50)
  if values["all_reserves"]:
    modded_text = f" ({config.MODDED})" if is_modded else ""
    _show_message(f"{config.LOADING_ANIMALS}{modded_text}: {config.get_species_name(species_key)} @ {config.LOOK_ALL_RESERVES}")
    species_description_full = populations.find_animals(species_key, modded=is_modded, good=values["good_ones"], top=is_top, progress_bar=window["progress"])
  else:
    species_description_full = populations.describe_animals(loaded_reserve.reserve_key, species_key, loaded_reserve.parsed_adf.adf, good=values["good_ones"], top=is_top, precision=4)
  _progress(90)
  species_description = [x[0:-1] for x in species_description_full]
  window["species_description"].update(species_description)
  adf_animals = [x[-1] for x in species_description_full]
  window["species_description"].metadata = adf_animals
  _progress(100)
  _show_species_description(window, loaded_reserve.reserve_key, species_key, is_modded, is_top)
  _show_message(f"{config.ANIMALS_LOADED}{f' ({config.MODDED})' if loaded_reserve.modded else ''}: {config.get_species_name(species_key)}")
  # _show_message("", delay=False)
  _progress(0)

def _parse_all_species_counts(loaded_reserve: adf.LoadedReserve) -> dict[str, dict]:
  all_species_counts = {}
  for species_data in loaded_reserve.population_description:
    species_counts = _parse_species_counts(window, {}, species_data=species_data)
    all_species_counts[species_counts["species_key"]] = species_counts
  return all_species_counts

def _parse_species_counts(window: sg.Window, values: dict, species_data: list = None) -> dict:
  if not species_data:
    loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
    if not loaded_reserve:
      _show_error(config.SELECT_A_RESERVE, delay=False)
      return None
    selected_rows = values["reserve_description"]
    if not selected_rows:
      # _show_error(config.SELECT_AN_ANIMAL, delay=False)
      return None
    species_data = loaded_reserve.population_description[selected_rows[0]]
  counts = {}
  counts["species_key"] = species_data[0]
  counts["total"] = int(species_data[3])
  counts["male"] = int(species_data[4])
  counts["female"] = int(species_data[5])
  counts["diamond"] = int(species_data[8])
  counts["great_one"] = int(species_data[9])
  return counts

def _toggle_section_visible(window: sg.Window, section: str, visible: bool = None) -> bool:
  opened = visible if visible != None else not window[section].visible
  window[f"{section}_symbol"].update(f"{symbol_open if opened else symbol_closed}")
  window[section].update(visible=opened)
  return opened


def main_window(my_window: sg.Window = None) -> sg.Window:
    save_path_value = config.get_save_path()
    reserve_name_size = len(max(config.reserve_names(), key = len))
    reserve_name_size = 27 if reserve_name_size < 27 else reserve_name_size

    global RESERVE_COLUMNS
    RESERVE_COLUMNS = [
        config.SPECIES,
        config.ANIMALS_TITLE,
        config.MALES,
        config.FEMALES,
        config.HIGH_WEIGHT,
        config.HIGH_SCORE,
        config.DIAMOND,
        config.GREATONE
    ]
    global SPECIES_COLUMNS
    SPECIES_COLUMNS = [
      config.RESERVE,
      config.LEVEL,
      config.GENDER,
      config.WEIGHT,
      config.SCORE,
      config.FUR,
      config.TROPHY_RATING,
    ]

    layout = [
      [
        sg.Image(logo.value),
        sg.Column([
          [sg.T(config.APC, expand_x=True, font="_ 24")],
          [sg.T(save_path_value, font=SMALL_FONT, k="save_path")]
        ]),
        sg.Push(),
        sg.T(f"{config.VERSION}: {__version__} ({config.DEFAULT}: {config.default_locale}, {config.USING}: {config.use_languages[0]})", font=SMALL_FONT, p=((0,0),(0,60)), right_click_menu=['',[f'{config.UPDATE_TRANSLATIONS}::update_translations', config.SWITCH_LANGUAGE, [f"{x}::switch_language" for x in config.SUPPORTED_LANGUAGES]]])
      ],
      [
        sg.T(f"{config.HUNTING_RESERVE}:", p=((0,0), (10,0)), k="reserve", metadata=None),
        sg.Combo(config.reserve_names(), s=(reserve_name_size,len(config.reserve_names())), k="reserve_name", enable_events=True, metadata=config.reserves(), p=((10,10), (10,0))),
        sg.pin(sg.Button(config.BACK_TO_RESERVE, k="show_reserve", font=SMALL_FONT, visible=False, p=((10,0), (10,0)))),
      ],
      [
        sg.Column([
          [
            sg.Checkbox(config.VIEW_MODDED_VERSION, key="load_modded", font=MEDIUM_FONT, enable_events=True, p=((0,0),(0,0))),
            sg.pin(sg.Text("", text_color="orange", key="modded_label", font=MEDIUM_FONT, p=((5,0),(0,0)))),
            sg.Push(),
            sg.Text(f"{config.TOTAL_ANIMALS}:", font=MEDIUM_FONT, p=((10,0),(0,0))),
            sg.Text("0", key="total_animals", font=MEDIUM_FONT, p=((5,5),(0,0))),
          ],
          [
            sg.Table(
              [],
              RESERVE_COLUMNS,
              k="reserve_description",
              metadata=None,
              font=MEDIUM_FONT,
              header_background_color="brown",
              cols_justification=("l", "r", "r", "r", "r", "r", "r", "r"),
              col_widths=[20,6,6,6,8,8,8,8],
              auto_size_columns=False,
              hide_vertical_scroll=True,
              expand_x=True,
              expand_y=True,
              enable_click_events=True,
              select_mode=sg.TABLE_SELECT_MODE_BROWSE,
            ),
            sg.Table(
              [],
              SPECIES_COLUMNS,
              k="species_description",
              metadata=[],
              font=MEDIUM_FONT,
              header_background_color="brown",
              visible=False,
              cols_justification=("l", "l", "c", "r", "r", "l", "c", "c"),
              col_widths=[17,7,3,3,3,9,8],
              auto_size_columns=False,
              expand_x=True,
              expand_y=True,
              enable_click_events=True,
              select_mode=sg.TABLE_SELECT_MODE_EXTENDED,
            ),
            sg.Table(
              [],
              [config.RESERVE, config.LOADED, config.MODDED_FILE],
              k="mod_list",
              metadata=None,
              font=MEDIUM_FONT,
              header_background_color="brown",
              visible=False,
              cols_justification=("l", "c", "l"),
              col_widths=[17, 4, 50],
              auto_size_columns=False,
              expand_x=True,
              expand_y=True,
              enable_click_events=True,
            )
          ],
        ], vertical_alignment="top", expand_x=True, expand_y=True),
        sg.Column([
          [sg.Text("", key="species_name", text_color="orange", justification="right", expand_x=True, p=((5,5),(0,0)))],
          [
            sg.Column([
              [
                sg.TabGroup([[
                  sg.Tab(config.MOD, [
                    [sg.T(textwrap.fill(config.MODIFY_ANIMALS, 30), font=MEDIUM_FONT, expand_x=True, justification="c", text_color="orange", p=(0,10))],
                    [
                      sg.T(symbol_closed, k="gender_section_symbol", enable_events=True, text_color="orange", p=((5,0),(0,0))),
                      sg.T(config.GENDER_COUNTS, k="gender_section_title", enable_events=True, text_color="orange", p=((5,0),(0,0)))
                    ],
                    [sg.pin(sg.Column([
                      [sg.Slider((0,0), orientation="h", expand_x=True, k="gender_value", enable_events=True, p=((10,10), (0,0)))],
                      [
                        sg.T("F", font=DEFAULT_FONT, p=((5,0),(10,0))),
                        sg.Input("0", s=5, p=((5,0), (10,0)), k="new_female_value", enable_events=True),
                        sg.Push(),
                        sg.Input("0", s=5, p=((0,5), (10,0)), k="new_male_value", enable_events=True),
                        sg.T("M", font=DEFAULT_FONT, p=((0,5), (10,0)))
                      ],
                      [sg.Checkbox(config.ADD_REMOVE_ANIMALS, k="add_remove_animals", font=MEDIUM_FONT, default=False, enable_events=True, p=((10,10),(10,0)))],
                    ], k="gender_section", visible=False))],
                    [
                      sg.T(symbol_open, k="trophy_section_symbol", enable_events=True, text_color="orange", p=((5,0),(10,0))),
                      sg.T(config.TROPHY_RATING, k="trophy_section_title", enable_events=True, text_color="orange", p=((5,0),(10,0)))
                    ],
                    [sg.pin(sg.Column([
                      [sg.T(f"{config.GREATONES}:", font=DEFAULT_FONT, p=((5,0),(5,0)))],
                      [sg.Slider((0,0), orientation="h", p=((10,10),(5,5)), k="great_one_value", enable_events=True)],
                      [sg.T(f"{config.DIAMONDS}:", font=DEFAULT_FONT, p=((5,0),(10,0))), sg.T("", p=((0,0),(10,0)), k="diamond_gender", font=MEDIUM_FONT, text_color="orange")],
                      [sg.Checkbox(config.USE_ALL_FURS, k="diamond_all_furs", font=MEDIUM_FONT, p=((10,10),(5,0)))],
                      [sg.Listbox([], k="diamond_furs", expand_x=True, p=((10,10),(5,5)), s=(None, 4), select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE)],
                      [sg.Slider((0,0), orientation="h", p=((10,10),(5,5)), k="diamond_value", enable_events=True)],
                    ], k="trophy_section", visible=True))],
                    [sg.Button(config.RESET, k="reset", font=BUTTON_FONT, p=((15,0),(20,10))), sg.Button(config.UPDATE_ANIMALS, expand_x=True, disabled=True, k="update_animals", font=BUTTON_FONT, p=((10,15),(20,10)))],
                  ], k="mod_tab", metadata={}),
                  sg.Tab(config.FURS, [
                    [sg.T(textwrap.fill(config.MODIFY_ANIMAL_FURS, 30), font=MEDIUM_FONT, expand_x=True, justification="c", text_color="orange", p=(0,10))],
                    [
                      sg.T(symbol_open, k="fur_male_section_symbol", enable_events=True, text_color="orange", p=((5,0),(0,0))),
                      sg.T(config.MALE_FURS, k="fur_male_section_title", enable_events=True, text_color="orange", p=((5,0),(0,0)))
                    ],
                    [sg.pin(sg.Column([
                        [sg.Checkbox(config.USE_ALL_FURS, k="male_all_furs", font=MEDIUM_FONT, p=((10,0),(5,5)))],
                        [sg.Listbox([], k="male_furs", expand_x=True, p=((10,10),(5,5)), s=(None, 4), select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE)],
                        [sg.Slider((0,0), orientation="h", p=((10,10),(5,5)), k="male_fur_animals_cnt")],
                    ], k="fur_male_section", visible=True))],
                    [
                      sg.T(symbol_closed, k="fur_female_section_symbol", enable_events=True, text_color="orange", p=((5,0),(10,0))),
                      sg.T(config.FEMALE_FURS, k="fur_female_section_title", enable_events=True, text_color="orange", p=((5,0),(10,0)))
                    ],
                    [sg.pin(sg.Column([
                      [sg.Checkbox(config.USE_ALL_FURS, k="female_all_furs", font=MEDIUM_FONT, p=((10,0),(5,5)))],
                      [sg.Listbox([], k="female_furs", expand_x=True, p=((10,10),(5,5)), s=(None, 4), select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE)],
                      [sg.Slider((0,0), orientation="h", p=((10,10),(5,5)), k="female_fur_animals_cnt")],
                    ], k="fur_female_section", visible=False))],
                    [sg.Button(config.RESET, k="fur_reset", font=BUTTON_FONT, p=((15,0),(20,10))), sg.Button(config.UPDATE_ANIMALS, expand_x=True, disabled=True, k="fur_update_animals", font=BUTTON_FONT, p=((10,15),(20,10)))],
                  ], k="fur_tab"),
                  sg.Tab(config.PARTY, [
                    [sg.T(textwrap.fill(config.CHANGE_ALL_SPECIES, 30), font=MEDIUM_FONT, expand_x=True, justification="c", text_color="orange", p=(0,10))],
                    [sg.T(textwrap.fill(config.PARTY_DESCRIPTION, 40), font=SMALL_FONT, expand_x=True, justification="c", p=((5,5),(0,10)))],
                    [sg.Slider((0,100), orientation="h", p=((0,0),(10,0)), k="great_one_party_percent")],
                    [sg.Button(config.GREATONE_PARTY, expand_x=True, disabled=True, k="great_one_party", font=BUTTON_FONT, button_color=(sg.theme_button_color()[1], "brown"), p=((15,15),(5,0)))],
                    [sg.Slider((0,100), orientation="h", p=((15,15),(10,0)), k="diamond_party_percent")],
                    [sg.Button(config.DIAMOND_PARTY, expand_x=True, disabled=True, k="diamond_party", font=BUTTON_FONT, button_color=(sg.theme_button_color()[1], "brown"), p=((15,15),(5,0)))],
                    # [sg.Slider((0,100), orientation="h", p=((10,10),(10,0)), k="everyone_party_percent")],
                    # [sg.Button(config.WE_ALL_PARTY, expand_x=True, disabled=True, k="everyone_party", font=BUTTON_FONT, button_color=(sg.theme_button_color()[1], "brown"), p=((15,15),(5,0)))],
                    [sg.Slider((0,100), orientation="h", p=((15,15),(10,0)), k="fur_party_percent")],
                    [sg.Button(config.FUR_PARTY, expand_x=True, disabled=True, k="fur_party", font=BUTTON_FONT, button_color=(sg.theme_button_color()[1], "brown"), p=((15,15),(5,0)))],
                    [sg.Slider((0,100), orientation="h", p=((15,15),(10,0)), k="rare_fur_party_percent")],
                    [sg.Button(config.RARE_FUR_PARTY, expand_x=True, disabled=True, k="rare_fur_party", font=BUTTON_FONT, button_color=(sg.theme_button_color()[1], "brown"), p=((15,15),(5,0)))],
                  ], k="party_tab", element_justification='center'),
                  sg.Tab(config.EXPLORE, [
                    [sg.T(textwrap.fill(config.EXPLORE_ANIMALS, 30), font=MEDIUM_FONT, expand_x=True, justification="c", text_color="orange", p=(0,10))],
                    [sg.Checkbox(config.DIAMONDS_AND_GREATONES, font=MEDIUM_FONT, default=False, k="good_ones")],
                    [sg.Checkbox(config.LOOK_MODDED_ANIMALS, font=MEDIUM_FONT, k="modded_reserves")],
                    [sg.Checkbox(config.LOOK_ALL_RESERVES, font=MEDIUM_FONT, k="all_reserves")],
                    [sg.Checkbox(config.ONLY_TOP_SCORES, font=MEDIUM_FONT, k="top_scores")],
                    [sg.Button(config.SHOW_ANIMALS, expand_x=True, k="show_animals", disabled=True, font=BUTTON_FONT, p=((15,15),(5,0)))]
                  ], k="explore_tab"),
                  sg.Tab(config.FILES, [
                    [sg.T(textwrap.fill(config.MANAGE_MODDED_RESERVES, 30), font=MEDIUM_FONT, expand_x=True, justification="c", text_color="orange", p=(0,10))],
                    [sg.Button(config.CONFIGURE_GAME_PATH, expand_x=True, k="set_save", font=BUTTON_FONT, p=((15,15),(5,0)))],
                    [sg.Button(config.LIST_MODS, expand_x=True, k="list_mods", font=BUTTON_FONT, p=((15,15),(5,0)))],
                    [sg.Button(config.LOAD_MOD, expand_x=True, k="load_mod", disabled=True, font=BUTTON_FONT, p=((15,15),(5,0)), metadata=False)],
                    [sg.Button(config.UNLOAD_MOD, expand_x=True, k="unload_mod", disabled=True, font=BUTTON_FONT, p=((15,15),(5,0)))],
                    [sg.Button(config.EXPORT_MOD, expand_x=True, k="export_mod", disabled=True, font=BUTTON_FONT, p=((15,15),(5,0)))],
                    [sg.Button(config.IMPORT_MOD, expand_x=True, k="import_mod", disabled=True, font=BUTTON_FONT, p=((15,15),(5,0)))],
                  ], k="files_tab", element_justification='center')
                ]], p=((0,0),(5,0)))
              ],
            ], vertical_alignment="top", p=((0,0),(0,0)), k="modding", visible=True),
            sg.Column([[
              sg.Frame(None, [
                [sg.T(textwrap.fill(config.ANIMAL_DETAILS, 30), font=MEDIUM_FONT, expand_x=True, justification="c", text_color="orange", p=(0,10))],
                [sg.T(f"{config.GREATONE}:", p=((10,0),(0,10))), sg.Combo([config.YES, config.NO], None, p=((20,0),(0,10)), k="animal_great_one", enable_events=True, disabled=True)],
                [sg.T(f"{config.GENDER}:", p=((10,0),(0,10))), sg.Combo([config.MALE, config.FEMALE], None, p=((20,0),(0,10)), k="animal_gender", enable_events=True, disabled=True)],
                # [sg.T(f"{config.TROPHY_RATING}:", p=((10,0),(0,10))), sg.Combo([config.YES, config.NO], None, p=((20,0),(0,10)), k="animal_great_one", enable_events=True, disabled=True)],
                [sg.Checkbox("", default=True, k="animal_weight_checkbox", p=((10,0),(10,0))), sg.T(f"{config.WEIGHT}:", p=((0,0),(10,0))), sg.T("", p=((0,0),(10,0)), k="animal_weight_info", font=MEDIUM_FONT, text_color="orange")],
                [sg.Slider((0,0), orientation="h", resolution=0.01, p=((20,10),(0,5)), k="animal_weight", enable_events=True)],
                [sg.Checkbox("", default=True, k="animal_score_checkbox", p=((10,0),(10,0))), sg.T(f"{config.SCORE}:", p=((00,0),(10,0))), sg.T("", p=((0,0),(10,0)), k="animal_score_info", font=MEDIUM_FONT, text_color="orange")],
                [sg.Slider((0,0), orientation="h", resolution=0.01, p=((20,10),(0,5)), k="animal_score", enable_events=True)],
                [sg.Checkbox("", default=True, k="animal_fur_checkbox", p=((10,0),(10,0))), sg.T(f"{config.FUR}:", p=((0,0),(10,0))), sg.T(f"({config.RANDOM_FUR})", p=((0,0),(10,0)), font=MEDIUM_FONT, text_color="orange")],
                [sg.Combo([],  p=((20,10),(5,5)), k="animal_fur", expand_x=True, disabled=True)],
                [sg.Button(config.RESET, k="animal_reset", font=BUTTON_FONT, p=((15,0),(20,10))), sg.Button(config.UPDATE_ANIMALS, expand_x=True, disabled=True, k="details_update_animals", font=BUTTON_FONT, p=((10,15),(20,10)))],
              ], relief=sg.RELIEF_RAISED, p=(0,5), expand_y=True)
            ]], k="exploring", vertical_alignment="top", p=((0,0),(0,0)), visible=False, metadata=False)
          ],
        ], vertical_alignment="top")
      ],
      [
        sg.ProgressBar(100, orientation='h', expand_x=True, s=(10,20), p=(10,5), key='progress')
      ],
      [
        sg.T("", text_color="orange", k="message_box", p=(5,5))
      ]
    ]

    window = sg.Window(config.APC, layout, resizable=True, font=DEFAULT_FONT, icon=logo.value, size=(1300, 800), finalize=True)

    if my_window is not None:
      my_window.close()
    return window

def main() -> None:
  sg.theme("DarkAmber")
  global window
  window = main_window()
  loaded_reserve = None
  _check_for_update()

  while True:
      event, values = window.read()
      logger.debug(event)
      if event == sg.WIN_CLOSED:
        break

      try:
        reserve_name = values.get("reserve_name")
        if event == "reserve_name" and reserve_name:
          _load_reserve_description(window, values, config.get_reserve_key_from_name(reserve_name))
          if window["reserve"].metadata is None:
            continue
          _show_reserve_description(window, values, window["reserve"].metadata.reserve_key)
        elif isinstance(event, tuple):
          row, col = event[2]
          loaded_reserve: adf.LoadedReserve = window["reserve"].metadata
          if event[0] == "reserve_description" and event[1] == "+CLICKED+" and loaded_reserve is not None:
            if row != None and row >= 0:
              _animal_selected(window, values, row)
          elif event[0] == "mod_list" and event[1] == "+CLICKED+":
            row, _ = event[2]
            if row != None and row >= 0:
              selected_mod = mods[row]
              window["load_mod"].update(disabled=False)
              window["export_mod"].update(disabled=False)
              window["import_mod"].update(disabled=False)
              window["unload_mod"].update(disabled=selected_mod[1] != config.YES)
          elif event[0] == "species_description" and event[1] == "+CLICKED+":
            if not (species_key := window["species_name"].metadata):
              _show_message(config.SELECT_AN_ANIMAL)
              continue
            if row != None:
              if row == -1:
                _sort_species_description(window, col)
              if row >= 0:
                animal_details = _parse_animal_row(window["species_description"].Values[row], species_key)
                _disable_animal_details(window, False)
                _update_animal_details(window, animal_details)
        elif event == "animal_great_one" or event == "animal_gender":
          if not (species_key := window["species_name"].metadata):
            _show_message(config.SELECT_AN_ANIMAL)
            continue
          if values["animal_great_one"] == config.YES:
            # Check if the user selected "Great One" for an invalid gender
            great_one_gender = config.get_great_one_gender(species_key)
            selected_gender = "male" if values["animal_gender"] == config.MALE else "female"
            print(selected_gender)
            if great_one_gender not in [selected_gender, "both"]:
              # Update the UI values for the proper Great One gender
              values["animal_gender"] = config.MALE if selected_gender == "female" else config.FEMALE
              window["animal_gender"].update(value= values["animal_gender"])
              print(values["animal_gender"])
              window.refresh()
          animal_details = _parse_animal_details(values, species_key)
          animal_details.fur_name = None
          animal_details.fur_key = None
          _update_animal_details(window, animal_details)
        elif event == "set_save":
          provided_path = sg.popup_get_folder(f"{config.SELECT_FOLDER}:", title=config.SAVES_PATH_TITLE, icon=logo.value, font=DEFAULT_FONT)
          if provided_path:
            config.write_save_path(provided_path)
            window["save_path"].update(provided_path)
            _show_message(config.PATH_SAVED)
        elif event == "show_animals":
          _show_animals(window, values)
        elif event == "show_reserve":
          if not (loaded_reserve := window["reserve"].metadata):
            _show_message(config.SELECT_A_RESERVE)
            continue
          _load_reserve_description(window, values, loaded_reserve.reserve_key)
          _show_reserve_description(window, values, loaded_reserve.reserve_key)
        elif event == "details_update_animals":
          if not (species_key := window["species_name"].metadata):
            _show_message(config.SELECT_AN_ANIMAL)
            continue
          selected_animal_rows = window["species_description"].SelectedRows
          if len(selected_animal_rows) > 0:
            logger.debug(f"MODDING {len(selected_animal_rows)} ANIMALS")
            selected_adf_animals = [window["species_description"].metadata[i] for i in selected_animal_rows]
            selected_animal_details = _parse_animal_details(values, species_key)
            selected_reserves = list({a.reserve_key for a in selected_adf_animals})
            logger.debug(f"{len(selected_reserves)} RESERVES")
            if len(selected_reserves) > 1:
              popup_title = f"{config.WARNING}: {len(selected_reserves)} {config.RESERVES_TITLE}"
              popup_message = f"{config.SELECTED_MULTIPLE_RESERVES}\n"
              for reserve in selected_reserves:
                popup_message += f"\n - {config.get_reserve_name(reserve)}  [{config.get_population_file_name(reserve)}]"
              confirm_mod_animals = _show_popup(popup_message, popup_title, config.OK, config.CANCEL)
              if not confirm_mod_animals == "ok":
                continue
            _mod_animals(window, values, species_key, selected_animal_details, selected_adf_animals)
            _show_animals(window, values, modded=True)
        elif event == "update_animals":
          if not (loaded_reserve := window["reserve"].metadata):
            _show_message(config.SELECT_A_RESERVE)
            continue
          if not (species_key := window["species_name"].metadata):
            _show_message(config.SELECT_AN_ANIMAL)
            continue
          male_value = int(window["new_male_value"].get())
          male_furs = window["male_furs"].metadata
          female_value = int(window["new_female_value"].get())
          female_furs = window["female_furs"].metadata
          all_species_counts = _parse_all_species_counts(loaded_reserve)
          all_species_counts[species_key]["total"] = male_value + female_value
          # if sum(count["total"] for count in all_species_counts.values()) > 50_000:
          #   _show_error(config.TOO_MANY_TOTAL_ANIMALS)
          #   continue
          great_one_value = int(values["great_one_value"])
          diamond_value = int(values["diamond_value"])
          diamond_furs = window["diamond_furs"].Values if values["diamond_all_furs"] or len(values["diamond_furs"]) == 0 else values["diamond_furs"]
          diamond_gender = config.get_diamond_gender(species_key)
          if diamond_gender == "male":
            male_use_furs = [male_furs["keys"][male_furs["names"].index(x)] for x in diamond_furs]
            female_use_furs = []
          elif diamond_gender == "female":
            male_use_furs = []
            female_use_furs = [female_furs["keys"][female_furs["names"].index(x)] for x in diamond_furs]
          else:
            label_pattern = r'\s\(\w+\)$'
            male_use_furs = [male_furs["keys"][male_furs["names"].index(re.sub(label_pattern, "", x))] for x in diamond_furs if f"({config.MALE.lower()})" in x]
            female_use_furs = [female_furs["keys"][female_furs["names"].index(re.sub(label_pattern, "", x))] for x in diamond_furs if f"({config.FEMALE.lower()})" in x]

          if not (species_counts := _parse_species_counts(window, values)):
            continue
          try:
            if male_value != species_counts["male"]:
              if values["add_remove_animals"]:
                _mod_animal_count(window, species_key, male_value - species_counts["male"], "male")
              elif male_value > species_counts["male"]:
                logger.debug("modding males")
                _mod(window, species_key, Strategy.males, male_value - species_counts["male"])
            if female_value != species_counts["female"]:
              if values["add_remove_animals"]:
                _mod_animal_count(window, species_key, female_value - species_counts["female"], "female")
              elif female_value > species_counts["female"]:
                logger.debug("modding females")
                _mod(window, species_key, Strategy.females, female_value - species_counts["female"])
            if _is_great_one_enabled(window, great_one_value):
              logger.debug("modding great_one")
              _mod(window, species_key, Strategy.great_one_some, great_one_value)
            if _is_diamond_enabled(window, diamond_value):
              logger.debug("modding diamonds")
              _mod_diamonds(window, species_key, diamond_value, male_use_furs, female_use_furs)
          except populations.NoAnimalsException as ex:
            _show_error(ex)

          _disable_new_reserve(window)
          _reset_mod(window)
          _clear_furs(window)
        elif event == "fur_update_animals":
          male_all_furs = values["male_all_furs"]
          female_all_furs = values["female_all_furs"]
          male_furs = window["male_furs"].metadata
          female_furs = window["female_furs"].metadata
          selected_male_fur_names = male_furs["names"] if male_all_furs else values["male_furs"]
          selected_male_furs = [male_furs["keys"][male_furs["names"].index(x)] for x in selected_male_fur_names]
          selected_female_fur_names = female_furs["names"] if female_all_furs else values["female_furs"]
          selected_female_furs = [female_furs["keys"][female_furs["names"].index(x)] for x in selected_female_fur_names]
          male_fur_cnt = int(values["male_fur_animals_cnt"])
          female_fur_cnt = int(values["female_fur_animals_cnt"])
          male_changing = (male_all_furs or len(selected_male_furs) > 0) and male_fur_cnt > 0
          female_changing = (female_all_furs or len(selected_female_furs) > 0) and female_fur_cnt > 0
          if male_changing or female_changing:
            _mod_furs(window, selected_male_furs, selected_female_furs, male_fur_cnt, female_fur_cnt)
        elif event == "fur_reset":
          _reset_furs(window)
        elif event == "animal_reset":
          selected_animal_rows = window["species_description"].SelectedRows
          species_key = window["species_name"].metadata
          if len(selected_animal_rows) > 0:
            animal_details = _parse_animal_row(window["species_description"].Values[selected_animal_rows[0]], species_key)
            _update_animal_details(window, animal_details)
        elif event == "load_modded":
          if loaded_reserve := window["reserve"].metadata:
            _load_reserve_description(window, values, loaded_reserve.reserve_key)
        elif event == "list_mods":
          mods = _process_list_mods(window, reserve_name)
        elif event == "load_mod":
          confirm = _show_popup(f"{config.CONFIRM_LOAD_MOD} \n\n{config.BACKUP_WILL_BE_MADE}\n", config.CONFIRMATION, config.OK, config.CANCEL)
          if confirm == "ok":
            _load_mod(window, selected_mod[2])
            mods = _process_list_mods(window)
        elif event == "unload_mod":
          _unload_mod(window, selected_mod[2])
          mods = _process_list_mods(window)
        elif event == "export_mod":
          from_mod = selected_mod[2]
          export_file = _show_export_popup(selected_mod[0], Path(from_mod).name)
          if export_file != None and export_file != "cancel":
            _copy_file(from_mod, export_file)
            sg.PopupQuickMessage(config.MOD_EXPORTED, font="_ 28", background_color="brown")
        elif event == "import_mod":
          to_mod = selected_mod[2]
          import_file = _show_import_popup(selected_mod[0], Path(to_mod).name)
          if import_file != '' and import_file != "cancel":
            _copy_file(import_file, to_mod)
            sg.PopupQuickMessage(config.MOD_IMPORTED, font="_ 28", background_color="brown")
        elif event == "reset":
          _reset_mod(window)
        elif event == "great_one_party":
          _run_party(
            window,
            values,
            "great_one",
            party_name=config.GREATONE_PARTY,
            display_name=config.GREATONE,
            more_display_name=config.GREATONES,
            complete_suffix=config.GREATONE_PARTY_COMPLETE,
            gender_func=config.get_great_one_gender,
            strategy_enum=Strategy.great_one_some,
          )
        elif event == "diamond_party":
           _run_party(
            window,
            values,
            "diamond",
            party_name=config.DIAMOND_PARTY,
            display_name=config.DIAMOND,
            more_display_name=config.DIAMONDS,
            complete_suffix=config.DIAMOND_PARTY_COMPLETE,
            gender_func=config.get_diamond_gender,
            strategy_enum=Strategy.diamond_some,
          )
        # elif event == "everyone_party":
        #   if not (loaded_reserve := window["reserve"].metadata):
        #     _show_message(config.SELECT_A_RESERVE)
        #     continue
        #   great_one_species = _get_great_one_species(loaded_reserve.reserve_key)
        #   for species_key in get_reserve_species(loaded_reserve.reserve_key):
        #     if species_key in great_one_species:
        #       _mod(window, species_key, Strategy.great_one_some, 10, percentage=True)
        #     _mod(window, species_key, Strategy.diamond_some, 50, rares=True, percentage=True)
        #     _mod(window, species_key, Strategy.furs_some, 100, rares=True, percentage=True)
        #   _disable_new_reserve(window)
        elif event == "fur_party":
          _run_fur_party(
              window,
              values,
              percent_key="fur_party_percent",
              party_label=config.FUR_PARTY,
              complete_suffix=config.FUR_PARTY_COMPLETE,
          )
        elif event == "rare_fur_party":
          _run_fur_party(
              window,
              values,
              percent_key="rare_fur_party_percent",
              party_label=config.RARE_FUR_PARTY,
              complete_suffix=config.RARE_FUR_PARTY_COMPLETE,
              rare=True,
          )
        elif "::" in event:
          value, key = event.split("::")
          if key == "update_translations":
            subprocess.Popen(f"pybabel compile --domain=apc --directory={config.APP_DIR_PATH / 'locale'}", shell=True)
            _show_popup(config.PLEASE_RESTART, config.APC, config.OK)
          elif key == "switch_language":
            config.update_language(value)
            window = main_window(window)
        elif event in ("gender_value", "great_one_value", "diamond_value", "new_female_value", "new_male_value", "add_remove_animals"):
          if event == "add_remove_animals":
            # FreeSimpleGUI does not change the slider appearance when disabled
            # Modify the underlying Tkinter widget
            slider = window["gender_value"]
            slider.update(disabled=values["add_remove_animals"])
            tk_slider = slider.Widget
            if values["add_remove_animals"]:
              tk_slider["troughcolor"] = "white"
            else:
              tk_slider["troughcolor"] = "#705e52"  # color for our theme: print(tk_slider["troughcolor"])
          if not (species_counts := _parse_species_counts(window, values)):
            continue
          if event == "gender_value":
            gender_value = int(values["gender_value"])
            changing = "male" if gender_value > 0 else "female"
          else:
            changing = event
          _update_mod_animal_counts(window, values, species_counts, changing=changing)
        elif event == "gender_section_symbol" or event == "gender_section_title":
          if not window["gender_section"].visible:
            _toggle_section_visible(window, "gender_section", True)
            _toggle_section_visible(window, "trophy_section", False)
        elif event == "trophy_section_symbol" or event == "trophy_section_title":
          if not window["trophy_section"].visible:
            _toggle_section_visible(window, "gender_section", False)
            _toggle_section_visible(window, "trophy_section", True)
        elif event == "fur_male_section_symbol" or event == "fur_male_section_title":
          if not window["fur_male_section"].visible:
            _toggle_section_visible(window, "fur_male_section", True)
            _toggle_section_visible(window, "fur_female_section", False)
        elif event == "fur_female_section_symbol" or event == "fur_female_section_title":
          if not window["fur_female_section"].visible:
            _toggle_section_visible(window, "fur_male_section", False)
            _toggle_section_visible(window, "fur_female_section", True)
      except Exception:
        _show_error_window(traceback.format_exc())

  window.close()

if __name__ == "__main__":
    main()