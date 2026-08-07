# Plan d'amélioration — plum_ecomax

Suivi de la revue du 2026-08-07 (protocole GAZ-MODEM/ecoNET, PDF constructeur
"Standard Transmission Protocols ed.15") et des correctifs qui ont suivi.

Légende : ✅ fait · 🔧 en cours · ⏳ à faire · ⏭️ hors scope pour l'instant (avec raison)

## 0. Corrigé avant ce plan (session précédente)

- ✅ `plum_transport.py` : import cassé `.plum_utils` → `.plum_protocol`
- ✅ `plum_device.py` : validation de trame durcie (CRC, longueur, `func`,
  adresse source, PID de réponse) — remplace le `any 0x68 ... ends with 0x16`
  d'origine
- ✅ `plum_device.py` : le code de résultat d'écriture (`0xE5`/`0x7D`/`0x7F`)
  est maintenant vérifié dans `_sync_set_value`
- ✅ `plum_device.py` : signedness SHORT_INT/WORD/DWORD corrigée dans
  `_encode`/`_decode`

## A. Fiabilité réseau / protocole

- [x] ✅ Verrou (`asyncio.Lock` sur `PlumDevice`) pour sérialiser toutes les
      I/O socket vers la chaudière — `get_value`/`get_values`/`set_value`
      passent tous par le même verrou, une écriture en tâche de fond et un
      cycle de polling ne peuvent plus ouvrir des connexions concurrentes
- [x] ✅ Lecture groupée : `PlumDevice.get_values()` +
      `_sync_get_values_batch()` construisent une trame 0x43 multi-blocs
      (un bloc par paramètre, comme documenté §1.5.3.12) au lieu d'une
      connexion TCP par paramètre. Branché à la fois dans
      `coordinator._async_update_data` (cycle de polling) et
      `_detect_available_parameters` (scan initial au démarrage)
- [ ] ⏭️ Connexion persistante / `plum_transport.py` comme transport
      canonique — reporté : changement d'architecture plus large, à traiter
      séparément une fois le verrou + le batching validés en prod

## B. Fiabilité des écritures

- [x] ✅ `coordinator.async_set_value`/`_perform_repeated_write` : arrête
      dès la première confirmation réelle (code `0xE5`), et si les 5
      tentatives échouent, restaure la valeur de cache précédente au lieu de
      laisser un état optimiste jamais confirmé
- [x] ✅ Le slug écrit est marqué "stale" (`_timestamps[slug] = 0`) après la
      tentative d'écriture (succès ou échec), donc le cycle de polling
      suivant relit la vraie valeur matérielle au lieu de faire confiance à
      l'état optimiste pendant tout le TTL de 5 minutes

## C. Conformité Home Assistant

- [x] ✅ `config_flow.py` : validation réelle de la connexion avant de créer
      l'entry — lecture protocolaire réelle d'un paramètre connu
      (`hdwstate`), pas juste un test de port TCP ouvert
- [x] ✅ `config_flow.py` : Options Flow (`PlumOptionsFlow`) pour
      reconfigurer IP/port/utilisateur/mot de passe/circuits sans supprimer
      l'intégration — même validation de connexion, met à jour l'entry et
      la recharge
- [x] ✅ `config_flow.py` : champ mot de passe masqué (`TextSelector` type
      password) ; champ "username" qui manquait dans les traductions ajouté
      au passage
- [x] ✅ `device_info` centralisé dans `device.py` (helpers
      `boiler_device_info`/`hdw_device_info`/`circuit_device_info`/
      `mixers_device_info`), réutilisé par les 7 fichiers de plateforme —
      corrige le `(DOMAIN, "plum_hdw")` non scopé et donne enfin un
      `device_info` à `select.py`. Au passage, `unique_id` de `switch.py`/
      `select.py` (qui utilisaient `f"{DOMAIN}_{slug}"`, collision possible
      entre deux config entries) scopé par `entry_id` comme `number.py`
- [x] ✅ Plateforme `diagnostics.py` (snapshot redacté : entry sans
      identifiants, état du coordinateur, `available_slugs`, dernière
      exception)
- [x] ✅ `async_setup_entry` lève `ConfigEntryNotReady` si
      `device.load_map()` échoue (le `load_map()` lève maintenant au lieu
      d'avaler l'exception)
- [x] ✅ Logging : f-strings + emojis → formatage paresseux `%s` dans tous
      les fichiers de la plateforme (`coordinator.py`, `plum_device.py`,
      `switch.py`, `select.py`, `water_heater.py`, ...)
- [x] ✅ `hacs.json` : `filename` (clé "plugin", pas "integration") retirée,
      `homeassistant` minimum ajouté (`2024.1.0`)
- [x] ✅ `manifest.json` : `integration_type: "hub"` ajouté
- [ ] ⏭️ `issue_registry` (repair issue sur erreur d'auth en écriture) —
      reporté, nice-to-have
- [ ] ⏭️ Capteur diagnostic "dernière lecture réussie" / compteur erreurs
      CRC — reporté, nice-to-have (en partie couvert par `diagnostics.py`)

## D. Tests (non-régression + unitaires)

Inspiré de la structure de
[iLLixM/jackery_home_cloud-ha](https://github.com/iLLixM/jackery_home_cloud-ha)
(séparation `tests/unit/` vs `tests/regression/`, tests AST statiques pour les
invariants structurels, fake socket/session au lieu de mocks profonds,
instances construites via `object.__new__` pour éviter de dépendre d'un hass
complet).

- [x] ✅ `tests/regression/test_rename_safety.py` — AST statique : tout
      `from .X import Y` doit correspondre à un nom réellement défini dans
      `X.py`. Vérifié qu'il aurait détecté le bug `plum_utils` de la
      section 0 (réintroduit temporairement puis retiré pour le test)
- [x] ✅ `tests/regression/test_unique_id_stability.py` — snapshot du
      `unique_id` réel (instanciation directe) des 7 plateformes
      d'entités
- [x] ✅ `tests/regression/test_device_info_scoping.py` — instancie chaque
      plateforme sous deux config entries différentes et vérifie qu'aucun
      identifiant de device n'est partagé. Vérifié qu'il aurait détecté le
      bug `(DOMAIN, "plum_hdw")` (réintroduit temporairement puis retiré)
- [x] ✅ `tests/unit/test_plum_protocol.py` — CRC16 (vecteurs tirés du PDF),
      `BoilerFrame.to_bytes`/`from_bytes` round-trip, `BoilerParameter`
      (bits modifiable/readable/type)
- [x] ✅ `tests/unit/test_plum_device.py` — `_extract_valid_frame` (trame
      valide du PDF, préfixe de bruit, CRC corrompu, trame tronquée,
      mauvaise source), `_encode`/`_decode` (tous les types, bornes
      signées/non signées), `_sync_get_value`/`_sync_set_value`/
      `_sync_get_values_batch` via faux socket (succès, PID différent,
      code de résultat d'écriture invalide, réponse fragmentée sur
      plusieurs `recv()`)
- [x] ✅ Test de concurrence pour le verrou asyncio (`TestIoSerialization`
      dans `test_plum_device.py`) — écriture + lectures concurrentes,
      vérifie qu'au plus une transaction socket est active à la fois
- [x] ✅ `tests/unit/test_coordinator_write_and_batch.py` — propagation
      d'échec d'écriture (confirmation au premier essai, retour à la
      valeur précédente après 5 échecs, cache vidé si pas de valeur
      précédente) + lecture groupée (cache frais ignoré, slugs périmés
      regroupés en un seul appel, fallback sur le cache si absent du lot)
- [x] ✅ `tests/unit/test_config_flow.py` — validation de connexion
      (succès, échec chargement de la map, pas de valeur retournée,
      exception réseau), schéma (mot de passe masqué, valeurs par défaut)
- [x] ✅ Corrigé au passage : `tests/test_water_heater.py` (signature du
      constructeur changée par le scoping `entry_id`) et
      `tests/test_coordinator.py` (le fixture appelait le vrai `__init__`
      de `DataUpdateCoordinator`, qui échoue avec `RuntimeError: Frame
      helper not set up` sur les versions récentes de `homeassistant`
      face à un `hass=MagicMock()` — bug préexistant, sans rapport avec ce
      diff, révélé seulement en faisant tourner la suite ; corrigé avec le
      même pattern `object.__new__`)
- **Résultat** : `93 passed` sur l'ensemble de `tests/` (venv Python 3.12,
  `homeassistant==2026.8.0`), 0 échec, 0 erreur

## F. Suite du 2026-08-07 (soir) — batching réel + inventaire des DP

- [x] ✅ Batching confirmé fonctionnel sur la vraie chaudière (192.168.1.38) :
      `get_value()` et `get_values()` renvoient des valeurs identiques sur
      plusieurs paramètres réels
- [x] ✅ Comportement empirique découvert (non documenté dans le PDF) : un
      seul PID invalide dans un lot fait échouer le lot entier (0 valeur
      reçue), même pour les PID valides du même lot. `scan_device_map.py`
      (nouveau script, réutilise `PlumDevice`) en tient compte et repasse
      en "un par un" pour les scans exploratoires du catalogue complet
- [x] ✅ Bug trouvé et corrigé : le type `RAW` (STRING du spec §1.4.2)
      n'était géré nulle part dans `_decode`/`_encode` → 14 paramètres
      (`uid`, noms de circuits, réglages wifi) décodaient toujours `None`,
      indiscernable d'une absence matérielle. Vérifié sur les 14/14 en
      conditions réelles après correctif (ex. `uid` = numéro de série réel,
      `circuit2name` = "RADIATEURS" — nom donné par l'utilisateur sur le
      panneau physique). `get_values()` exclut les slugs `RAW` du batching
      (longueur variable, pas de préfixe de taille sur le fil) et les lit
      individuellement à la place
- [x] ✅ `tempcircuit1`/`circuit6thermostattemp` retirés de `SENSOR_TYPES`
      (n'existent dans aucune device map, jamais d'entité possible) — pas
      un bug fonctionnel comme supposé initialement : `climate.py` a déjà
      un fallback (`circuitNthermostattemp` → `tempcircuitN`) qui couvre
      correctement les circuits 1 et 6
- [x] ✅ `DP_INVENTORY.md` : inventaire complet des 404 paramètres qui
      répondent sur cette chaudière mais ne sont pas encore des entités
      HA, groupés par thème (planning hebdo, circuits, ballon tampon,
      source de chaleur, mixeurs, ECS/anti-légionellose, réseau, alarmes)
- [x] ✅ Première vague de nouvelles entités choisie avec l'utilisateur et
      implémentée + vérifiée en direct sur la chaudière : cycle
      anti-légionellose (`hdwstartlegion` switch, `hdwlegionsetpoint`/
      `hdwlegionday`/`hdwlegionhour` number), noms de circuits
      (`circuit1name`..`circuit7name` sensor) et courbes de chauffe par
      circuit (`circuitNcurvefloor`/`curveradiator`/`basetemp`/
      `tempreduction` number, absent pour le circuit 6 qui n'a pas de
      registre de courbe dans la device map)

## G. Bugs trouvés en testant "pourquoi hdwpumpforce ne marche pas" (2026-08-07 soir)

Investigation partie de l'observation de l'utilisateur ("j'ai l'impression
que hdwpumpforce ne marche pas car il faut le mode administrateur manuel
sur l'écran"). Testé directement sur la chaudière avec écriture réelle +
lecture du résultat sur le fil :

- [x] ✅ **Cause réelle n°1** : `_sync_set_value` exigeait un code de
      résultat explicite (`0xE5`) dans la réponse d'écriture, conforme à
      l'exemple du PDF (§1.5.3.10). Mais cette chaudière/ce firmware
      acquitte une écriture réussie avec une trame `func=0xA9` **sans
      aucune donnée** (`l_val=5`, pas de byte de code du tout) — confirmé
      en capturant les octets bruts sur le fil. Résultat : **toutes les
      écritures étaient rapportées comme échouées, y compris quand elles
      réussissaient réellement** (vérifié par relecture : la valeur
      changeait bien et persistait). Corrigé : un payload vide compte
      maintenant comme succès ; un payload non vide est toujours vérifié
      contre `0xE5` (pour rester compatible avec un firmware qui, lui,
      envoie le code explicite)
- [x] ✅ **Cause réelle n°2** : `SWITCH_TYPES`/`SELECT_TYPES` étaient
      absents de la liste de sondage de `_detect_available_parameters` —
      donc `hdwpumpforce` (et tous les autres switches/selects) n'était
      jamais dans `available_slugs`, donc jamais relu par
      `_async_update_data`. Comme `DataUpdateCoordinator.data` est
      **remplacé en entier** à chaque cycle (pas fusionné — vérifié dans
      le code source `homeassistant.helpers.update_coordinator`), l'état
      optimiste d'un switch retombait à "inconnu" au cycle de polling
      suivant (30s), quel que soit l'état réel du matériel. Corrigé :
      ajoutés à la liste de sondage
- [x] ✅ Vérifié en bout en bout sur la vraie chaudière après les deux
      correctifs : écriture ON confirmée, relue correctement après un
      cycle de polling simulé, remise à OFF confirmée
- [x] ⚠️ **Constat sécurité, pas un bug du code** : en testant le
      correctif n°1, écriture tentée avec un mot de passe **volontairement
      faux** (`WRONGPASS` au lieu de `0000`) — acceptée quand même, la
      valeur a changé sur le matériel. Cette chaudière/ce firmware ne
      semble pas valider les identifiants d'écriture sur cette commande
      (au moins pour ce paramètre). Le champ mot de passe de l'intégration
      n'est donc pas la vraie barrière de sécurité ici — c'est la
      ségrégation réseau de la chaudière qui compte. Non testé sur
      d'autres paramètres/commandes ; à garder en tête, pas un correctif
      de code possible côté intégration

## H. Résolution finale : pourquoi hdwpumpforce semblait ne rien faire physiquement

Après les deux correctifs logiciels ci-dessus, `hdwpumpforce` acceptait et
tenait l'écriture, mais aucune télémétrie ne montrait d'effet physique sur
2 minutes complètes (température ballon/ECS stables, aucun bit d'état
pompe qui bouge). L'hypothèse initiale de l'utilisateur ("il faut le mode
administrateur manuel") était la bonne piste — confirmé par une procédure
manuelle sur le panneau physique avec horodatage de chaque étape, corrélé
au log de télémétrie continue (`scratchpad/manual_mode_correlation.log`) :

| Heure | Action panneau | Confirmé par télémétrie |
|---|---|---|
| 17:22:51 | Entrée mode manuel | `heatsourcemainpumpstate` déjà à 64 |
| ~17:22:55 | Lancer la pompe (bouton panneau) | `hdwpumpforce` 0→512 |
| ~17:23:15 | Arrêter la pompe | `hdwpumpforce` 512→0 |
| 17:23:25 | Sortie mode manuel | `heatsourcemainpumpstate` 64→0 (détecté 17:23:38) |

Ce qui est **solide** (confirmé à deux reprises indépendamment, y compris
par observation physique directe de l'utilisateur) :
- **Le paramètre est le bon.** Le bouton "pompe" du panneau en mode
  manuel écrit exactement le même registre (`hdwpumpforce`, id 172) que
  notre switch — confirmé indépendamment du protocole ecoNET.
- **Le forçage n'a d'effet physique que lorsque le panneau est en mode
  manuel.** Confirmé par la température ECS (`tempcwu`), qui a baissé de
  71.4°C à 68.0°C pendant que la pompe forcée tournait en mode manuel
  (preuve physique indépendante de toute télémétrie d'état), et
  reconfirmé verbalement par l'utilisateur après une deuxième
  manipulation physique.

**`heatsourcemainpumpstate` bit 6 (valeur 64) EST confirmé comme
indicateur fiable de "mode manuel actif"** — sur 3 tests physiques
au total :
- Test 1 (17:22-17:23) : à 64 tout le temps où le panneau était en
  manuel, retombé à 0 à la sortie.
- Test 2 (17:28-17:43, `scratchpad/manual_entry_fast.log`) : resté à 0
  sur ~15 min, cycle non reproduit — explication la plus probable :
  cycle trop rapide pour être capturé (voir test 3).
- **Test 3** (17:59-18:02, `scratchpad/manual_hold_test.log`), avec
  entrée en manuel maintenue délibérément ~1min46 avant de sortir :
  passé à 64 16s après le début de la procédure d'entrée (17:59:10 →
  détecté 17:59:26), revenu à 0 après la sortie (18:02:10 → confirmé
  18:02:33). **Reproduction propre, sans ambiguïté.**

Le test 2 est donc très probablement un cycle trop rapide (l'utilisateur
lui-même a soupçonné ne pas avoir attenu ~30s), pas une infirmation du
signal. Détail non éclairci : le délai de ~16-23s entre l'action
rapportée et la détection pourrait être du bruit de sondage normal, ou un
vrai délai de latence côté chaudière — pas déterminant, pas besoin
d'aller plus loin pour l'usage pratique (le bit est fiable une fois le
mode réellement entré/sorti).

Tentative d'écriture directe sur `heatsourcemainpumpstate` : rejetée
par la chaudière (`func=0x7F`, "invalid parameters") — c'est un champ
d'état en lecture seule ; impossible de forcer le mode manuel depuis
l'intégration par ce biais, seul le panneau physique peut l'activer.

Piste d'amélioration possible (non implémentée, à discuter) : exposer
`heatsourcemainpumpstate` bit 6 comme capteur binaire "Mode manuel actif"
dans HA, et/ou avertir l'utilisateur dans l'UI du switch `hdwpumpforce`
que l'écriture n'aura d'effet que si ce mode est actif sur le panneau
physique.

Tentative demandée d'activer le mode manuel **depuis le logiciel** (sans
passer par le panneau physique) : recherche élargie dans les 594
paramètres du catalogue pour tout ce qui ressemble à "force"/"override"/
"remote"/"ext"/"lock". Un seul candidat trouvé (`heatsourcemainpumpext`,
id 464) en plus de `heatsourcemainpumpstate` (déjà confirmé lecture
seule) — mais son rôle exact (bitmask non documenté) est inconnu, et
deviner des valeurs de bits sur le registre de la pompe principale de
la source de chaleur (pas seulement le circuit ECS/solaire isolé) risque
d'affecter le comportement réel du chauffage de façon imprévisible.
Sur demande explicite de l'utilisateur d'essayer quand même, tentative
unique et contrôlée : lecture de l'état de base
(`heatsourcemainpumpext=3`), écriture de `3 | 0x40 = 67` (le seul bit
pour lequel on a une preuve, ailleurs, de corrélation avec le mode
manuel), surveillance de `heatsourcemainpumpstate` et d'une dizaine
d'autres champs, puis restauration immédiate à `3`.

Résultat :
- **`heatsourcemainpumpext` est réellement modifiable** (écriture
  confirmée, valeur relue = 67) — contrairement à
  `heatsourcemainpumpstate` qui avait été rejeté (`0x7F`).
- **Aucun effet observé** : `heatsourcemainpumpstate` est resté à 0,
  aucune alarme, aucun autre champ surveillé n'a bougé au-delà du
  refroidissement passif normal de `tempcwu`.
- Restauré à la valeur d'origine (3), confirmé.

Résultat négatif propre, sans effet de bord, déjà annulé. Pas d'autre
bit à tester avec un raisonnement solide — au-delà de celui-ci, ce
serait deviner à l'aveugle sur un registre non documenté.
**Conclusion inchangée** : le mode manuel est très probablement une
porte de sécurité volontairement limitée à l'accès physique, pas
accessible via ecoNET avec ce qui est dans le catalogue de 594
paramètres.

## I. Nettoyage UI (2026-08-07 soir)

- [x] ✅ Numéro de série (`uid`) déplacé de capteur séparé vers
  `DeviceInfo.serial_number` sur le device "Plum EcoMAX Boiler" — plus
  idiomatique HA (visible sur la fiche de l'appareil, pas comme entité).
  Le slug reste sondé via le nouveau `DEVICE_INFO_PARAMS` dans const.py
  pour que `coordinator.data["uid"]` reste alimenté malgré la suppression
  de l'entité. Vérifié en direct sur la chaudière.
- [x] ✅ `calendar.py` ne posait pas `has_entity_name = True` ni
  `translation_key`, contrairement à toutes les autres plateformes de
  l'intégration (utilisait `_attr_name` codé en dur, sans traduction).
  Corrigé pour suivre le même schéma que `climate.py` (translation_key
  unique `"schedule"`, le nom de l'entité composé avec le nom du device
  par HA). Tests mis à jour en conséquence.
- [x] ✅ **Bug confirmé par capture d'écran** : `number.py` ne
  redirigeait vers un device dédié QUE les slugs `mixer*` — tout le
  reste (courbes de chauffe par circuit, réglages ECS `hdw*`) tombait
  sur le device générique "Plum EcoMAX Boiler", d'où l'écran montrant
  une dizaine de contrôles tous nommés "Plum EcoMAX…" (nom du device
  tronqué, faute de nom d'entité propre affiché dans ce contexte).
  Corrigé : les slugs `circuitN*` vont maintenant sur leur device
  `Circuit N`, les slugs `hdw*` sur le device `DHW`, `mixer*` sur
  `Mixers`, le reste (ex. `buforlongloadtime`) reste sur le boiler.
  Nouveau test de régression dédié (`TestNumberRoutedToCorrectDeviceCategory`)
  — les tests d'entry-scoping existants ne l'auraient pas détecté (un
  device incorrect mais correctement scopé par entry_id passe quand même
  ce test-là).
- [x] ✅ Demande "avertissement/confirmation avant modification" pour les
  courbes de chauffe : les slugs `circuitN*` (courbes/temp de base/
  réduction nocturne) et `hdwlegion*`/`buforlongloadtime` sont marqués
  `entity_category = EntityCategory.CONFIG`, ce qui les sort de la carte
  "Controls" principale vers la section "Configuration" du device — clic
  supplémentaire requis, moins exposé par accident. **Limite à noter** :
  ceci n'est PAS une vraie boîte de dialogue de confirmation — HA n'a pas
  de mécanisme intégré pour ça côté intégration ; une confirmation "es-tu
  sûr ?" est une fonctionnalité de dashboard Lovelace (`confirmation:` sur
  une carte), pas quelque chose que le code Python de l'entité peut
  imposer.
- **Important pour l'utilisateur** : ces deux correctifs nécessitent un
  **redémarrage complet de HA** (pas juste un rechargement de
  l'intégration) après déploiement, car le regroupement par device ET les
  traductions d'entités sont mis en cache côté frontend.
- [x] ✅ **Diagnostic (via l'API réelle de l'instance déployée)** : le
  "toujours nommé comme le device" touche 100% des entités `number.*`
  (30/30) + le switch `hdwstartlegion` + les 2 calendriers — tous créés
  ou modifiés ce soir. Les entités stables depuis avant ce soir (2 des 3
  switches, le select DHW, le water_heater, le climate) affichent un nom
  composé correct. **Ce n'est pas un bug de code actuel** : c'est le nom
  calculé et mis en cache dans le registre d'entités HA au moment de la
  création/mise à jour, probablement pendant une fenêtre où les
  traductions n'étaient pas encore chargées (race au démarrage). Corriger
  les fichiers de traduction ne le répare pas rétroactivement. **Fix
  recommandé à l'utilisateur** : supprimer puis ré-ajouter l'intégration
  entière (Paramètres → Appareils et services → Plum EcoMAX → Supprimer,
  puis reconfigurer), ce qui force une recréation propre de toutes les
  entités. Effet de bord positif attendu : élimine aussi les doublons
  orphelins repérés (`select.mode_ecs` vs `select.dhw_mode_ecs`,
  `calendar.calendrier` vs les 2 nouveaux calendriers).
- [x] ✅ **Bug signalé par l'utilisateur, confirmé et corrigé** :
  `number.py` était la seule plateforme à ignorer complètement
  `CONF_ACTIVE_CIRCUITS` — `sensor.py`/`climate.py`/`calendar.py` filtrent
  déjà les entités `circuitN*` par circuit actif, mais `number.py`
  créait les courbes de chauffe pour les 7 circuits du catalogue,
  indépendamment de la configuration ("chez moi, seul le circuit 2 est
  utilisé"). Corrigé pour suivre exactement le même filtre que les autres
  plateformes (slugs `circuitN*` ignorés si N n'est pas dans
  `CONF_ACTIVE_CIRCUITS`) ; les slugs `mixerN*` restent toujours créés,
  cohérent avec le comportement déjà choisi dans `sensor.py`. Nouveau
  test dédié (`tests/unit/test_number_setup.py`).
- [x] ✅ **Bug signalé par l'utilisateur, corrigé** : cliquer sur
  "Reconfigurer" renvoyait `500 Internal Server Error`. Cause :
  `PlumOptionsFlow.__init__` faisait `self.config_entry = config_entry`,
  mais sur la version HA installée, `OptionsFlow.config_entry` est
  maintenant une **propriété en lecture seule** (calculée depuis
  `self.hass`/`self.handler`, indisponible avant la fin de
  l'initialisation) — l'assignation levait `AttributeError: can't set
  attribute`, avant même qu'une réponse HTTP puisse être construite.
  C'était le risque que j'avais moi-même noté en écrivant ce code initial
  sans le vérifier contre la version HA réellement installée. Corrigé en
  supprimant `__init__` : le framework instancie `PlumOptionsFlow()` sans
  argument et positionne `hass`/`handler` après coup, rendant
  `self.config_entry` utilisable normalement dans `async_step_init`.
  Reproduit l'erreur exacte de l'utilisateur avec l'ancien code contre le
  vrai `OptionsFlow` de HA (pas un stub) avant de corriger, pour être sûr
  du diagnostic. Nouveau test de régression
  (`TestOptionsFlowConstruction`), vérifié qu'il aurait attrapé le bug en
  le réintroduisant temporairement.

## E. Suivi

- Repo : `github.com/lachand/plum_ecomax` (déployé via HACS sur
  `maison.lachand-pascal.fr`)
- Rien n'est commité automatiquement — à valider avant `git commit`/`push`
- Fichiers ajoutés : `custom_components/plum_ecomax/device.py`,
  `custom_components/plum_ecomax/diagnostics.py`,
  `tests/unit/*`, `tests/regression/*`
- Non fait, volontairement hors scope de cette session (voir ⏭️
  ci-dessus) : connexion persistante (remplacement du "une connexion TCP
  par transaction"), `issue_registry`, capteur diagnostic dédié
