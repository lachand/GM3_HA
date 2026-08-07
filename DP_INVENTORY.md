# Inventaire des DP — candidats non exposés dans HA

Scan du 2026-08-07 16:09, boîtier 192.168.1.38 (`scan_device_map.py` +
re-vérification manuelle des faux négatifs — voir méthodologie ci-dessous).

**570 paramètres répondent** sur cette chaudière sur les 594 du catalogue
(`device_map_ecomax360i.json`), dont **404 ne sont pas encore des entités
HA**. Regroupés ci-dessous par thème pour faciliter le tri.

## Méthodologie (pourquoi ces chiffres, pas les chiffres bruts du premier scan)

- Un scan "une tentative par paramètre" génère de faux négatifs (bruit
  réseau réel contre le matériel physique) : sur les 54 signalés "sans
  réponse" au premier passage, 16 répondaient en fait bien une fois
  re-testés avec plus de tentatives.
- 14 des paramètres restants "absents" ne l'étaient pas non plus : ce sont
  les paramètres de type `RAW` (`uid`, noms de circuits, réglages wifi),
  que le driver ne savait pas du tout décoder (toujours `None`, quel que
  soit ce que répond la chaudière). Corrigé dans `plum_device.py`
  (`_decode`/`_encode` gèrent maintenant `RAW` comme une chaîne
  terminée par un octet `00`, conformément au §1.4.2 du PDF constructeur),
  vérifié sur les 14/14 en conditions réelles.
- **24 paramètres restent confirmés absents** après re-vérification (4
  tentatives, deux passages) : tout ce qui touche `addsoruce*` (source de
  chaleur additionnelle solide, non applicable à un ecoMAX gaz),
  `mixer1valve*` (mixer 1 non câblé — cohérent avec `circuit1active=0`),
  et quelques réglages avancés (`circuitNcurveshift`, `circuitNusercor`,
  `weathertemp*delta*`). Liste complète dans `dp_scan_*.json`.

## Planning hebdo (bitmasks jour/AM-PM) (42)

| Slug | Valeur actuelle |
|---|---|
| `buforfridayam` | `16777215` |
| `buforfridaypm` | `16777215` |
| `buformondayam` | `16777215` |
| `buformondaypm` | `16777215` |
| `buforsaturdayam` | `16777215` |
| `buforsaturdaypm` | `16777215` |
| `buforsundayam` | `16777215` |
| `buforsundaypm` | `16777215` |
| `buforthursdayam` | `16777215` |
| `buforthursdaypm` | `16777215` |
| `bufortuesdayam` | `16777215` |
| `bufortuesdaypm` | `16777215` |
| `buforwednesdayam` | `16777215` |
| `buforwednesdaypm` | `16777215` |
| `circulationfridayam` | `16773120` |
| `circulationfridaypm` | `1048575` |
| `circulationmondayam` | `16773120` |
| `circulationmondaypm` | `1048575` |
| `circulationsaturdayam` | `16773120` |
| `circulationsaturdaypm` | `1048575` |
| `circulationsundayam` | `16773120` |
| `circulationsundaypm` | `1048575` |
| `circulationthursdayam` | `16773120` |
| `circulationthursdaypm` | `1048575` |
| `circulationtuesdayam` | `16773120` |
| `circulationtuesdaypm` | `1048575` |
| `circulationwednesdayam` | `16773120` |
| `circulationwednesdaypm` | `1048575` |
| `heatsourcefridayam` | `16777215` |
| `heatsourcefridaypm` | `16777215` |
| `heatsourcemondayam` | `16777215` |
| `heatsourcemondaypm` | `16777215` |
| `heatsourcesaturdayam` | `16777215` |
| `heatsourcesaturdaypm` | `16777215` |
| `heatsourcesundayam` | `16777215` |
| `heatsourcesundaypm` | `16777215` |
| `heatsourcethursdayam` | `16777215` |
| `heatsourcethursdaypm` | `16777215` |
| `heatsourcetuesdayam` | `16777215` |
| `heatsourcetuesdaypm` | `16777215` |
| `heatsourcewednesdayam` | `16777215` |
| `heatsourcewednesdaypm` | `16777215` |

## Circuits — courbes de chauffe & limites (81)

| Slug | Valeur actuelle |
|---|---|
| `circuit1basetemp` | `55` |
| `circuit1curvefloor` | `0.3` |
| `circuit1curveradiator` | `1.2` |
| `circuit1downhist` | `1.0` |
| `circuit1maxsettemprad` | `70` |
| `circuit1maxtempfloor` | `45` |
| `circuit1maxtempheat` | `55` |
| `circuit1maxtempheathist` | `5` |
| `circuit1minsettemp` | `55` |
| `circuit1minsettemprad` | `20` |
| `circuit1mintempfloor` | `20` |
| `circuit1multiplier` | `4.0` |
| `circuit1tempreduction` | `5` |
| `circuit2basetemp` | `40` |
| `circuit2curvefloor` | `0.3` |
| `circuit2curveradiator` | `1.3` |
| `circuit2downhist` | `1.0` |
| `circuit2maxsettempfloor` | `45` |
| `circuit2maxsettemprad` | `70` |
| `circuit2maxtempheat` | `55` |
| `circuit2maxtempheathist` | `5` |
| `circuit2minsettempfloor` | `20` |
| `circuit2minsettemprad` | `20` |
| `circuit2multiplier` | `4.0` |
| `circuit2tempreduction` | `5` |
| `circuit3basetemp` | `40` |
| `circuit3curvefloor` | `0.3` |
| `circuit3curveradiator` | `1.2` |
| `circuit3downhist` | `1.0` |
| `circuit3maxsettemp` | `70` |
| `circuit3maxsettempfloor` | `45` |
| `circuit3maxtempheat` | `55` |
| `circuit3maxtempheathist` | `5` |
| `circuit3minsettemp` | `20` |
| `circuit3minsettempfloor` | `20` |
| `circuit3multiplier` | `4.0` |
| `circuit3tempreduction` | `5` |
| `circuit4basetemp` | `40` |
| `circuit4curvefloor` | `0.3` |
| `circuit4curveradiator` | `1.2` |
| `circuit4downhist` | `1.0` |
| `circuit4maxsettempfloor` | `45` |
| `circuit4maxsettemprad` | `70` |
| `circuit4maxtempheat` | `55` |
| `circuit4maxtempheathist` | `5` |
| `circuit4minsettempfloor` | `20` |
| `circuit4minsettemprad` | `20` |
| `circuit4multiplier` | `4.0` |
| `circuit4tempreduction` | `5` |
| `circuit5basetemp` | `40` |
| `circuit5curvefloor` | `0.3` |
| `circuit5curveradiator` | `1.2` |
| `circuit5downhist` | `1.0` |
| `circuit5maxsettempfloor` | `45` |
| `circuit5maxsettemprad` | `70` |
| `circuit5maxtempheat` | `55` |
| `circuit5maxtempheathist` | `5` |
| `circuit5minsettempfloor` | `20` |
| `circuit5minsettemprad` | `20` |
| `circuit5multiplier` | `4.0` |
| `circuit5tempreduction` | `5` |
| `circuit6basetemp` | `40` |
| `circuit6downhist` | `1.0` |
| `circuit6maxsettemprad` | `70` |
| `circuit6maxtempheat` | `55` |
| `circuit6maxtempheathist` | `5` |
| `circuit6minsettemprad` | `20` |
| `circuit6multiplier` | `4.0` |
| `circuit6tempreduction` | `5` |
| `circuit7basetemp` | `40` |
| `circuit7curvefloor` | `0.3` |
| `circuit7curveradiator` | `1.2` |
| `circuit7downhist` | `1.0` |
| `circuit7maxsettempfloor` | `45` |
| `circuit7maxsettemprad` | `70` |
| `circuit7maxtempheat` | `55` |
| `circuit7maxtempheathist` | `5` |
| `circuit7minsettempfloor` | `20` |
| `circuit7minsettemprad` | `20` |
| `circuit7multiplier` | `4.0` |
| `circuit7tempreduction` | `5` |

## Circuits — état/debug/adressage (88)

| Slug | Valeur actuelle |
|---|---|
| `circuit1active` | `0` |
| `circuit1calctemp` | `0.0` |
| `circuit1longloading` | `0` |
| `circuit1mixercoolbasetemp` | `20` |
| `circuit1mixerstate` | `0` |
| `circuit1pumpdebug` | `0` |
| `circuit1settings` | `8482942` |
| `circuit1state` | `0` |
| `circuit1thermostataddress` | `100` |
| `circuit1thermostatsettings` | `1` |
| `circuit1typesettings` | `1` |
| `circuit2active` | `1` |
| `circuit2calctemp` | `20.0` |
| `circuit2inputdigitallogic` | `0` |
| `circuit2longloading` | `0` |
| `circuit2maxtimeswitching` | `1200` |
| `circuit2mintimeswitching` | `1` |
| `circuit2mixercoolbasetemp` | `20` |
| `circuit2mixerstate` | `0` |
| `circuit2pumpdebug` | `10` |
| `circuit2settings` | `8412543` |
| `circuit2state` | `75759618` |
| `circuit2thermostataddress` | `100` |
| `circuit2thermostatsettings` | `1` |
| `circuit2typesettings` | `1` |
| `circuit3active` | `0` |
| `circuit3calctemp` | `0.0` |
| `circuit3inputdigitallogic` | `0` |
| `circuit3longloading` | `0` |
| `circuit3maxtimeswitching` | `1200` |
| `circuit3mintimeswitching` | `1` |
| `circuit3mixercoolbasetemp` | `20` |
| `circuit3mixerstate` | `0` |
| `circuit3pumpdebug` | `0` |
| `circuit3settings` | `8409214` |
| `circuit3state` | `0` |
| `circuit3thermostataddress` | `102` |
| `circuit3thermostatsettings` | `1` |
| `circuit3typesettings` | `1` |
| `circuit4active` | `0` |
| `circuit4calctemp` | `0.0` |
| `circuit4inputdigitallogic` | `0` |
| `circuit4longloading` | `0` |
| `circuit4maxtimeswitching` | `1200` |
| `circuit4mintimeswitching` | `1` |
| `circuit4mixercoolbasetemp` | `20` |
| `circuit4mixerstate` | `0` |
| `circuit4pumpdebug` | `0` |
| `circuit4settings` | `8409214` |
| `circuit4state` | `0` |
| `circuit4thermostataddress` | `103` |
| `circuit4thermostatsettings` | `1` |
| `circuit4typesettings` | `1` |
| `circuit5active` | `0` |
| `circuit5calctemp` | `0.0` |
| `circuit5inputdigitallogic` | `0` |
| `circuit5longloading` | `0` |
| `circuit5maxtimeswitching` | `1200` |
| `circuit5mintimeswitching` | `1` |
| `circuit5mixercoolbasetemp` | `20` |
| `circuit5mixerstate` | `0` |
| `circuit5pumpdebug` | `0` |
| `circuit5settings` | `8409214` |
| `circuit5state` | `0` |
| `circuit5thermostataddress` | `104` |
| `circuit5thermostatsettings` | `1` |
| `circuit5typesettings` | `1` |
| `circuit6active` | `0` |
| `circuit6calctemp` | `0.0` |
| `circuit6inputdigitallogic` | `0` |
| `circuit6mixercoolbasetemp` | `20` |
| `circuit6mixerstate` | `0` |
| `circuit6pumpdebug` | `0` |
| `circuit6settings` | `8409214` |
| `circuit6state` | `0` |
| `circuit6thermostataddress` | `105` |
| `circuit7active` | `0` |
| `circuit7calctemp` | `0.0` |
| `circuit7inputdigitallogic` | `0` |
| `circuit7longloading` | `0` |
| `circuit7mixercoolbasetemp` | `20` |
| `circuit7mixerstate` | `0` |
| `circuit7pumpdebug` | `0` |
| `circuit7settings` | `8409214` |
| `circuit7state` | `0` |
| `circuit7thermostataddress` | `106` |
| `circuit7thermostatsettings` | `1` |
| `circuit7typesettings` | `1` |

## Circuits — noms & couleurs UI (15)

| Slug | Valeur actuelle |
|---|---|
| `circuit1name` | `H1` |
| `circuit2name` | `RADIATEURS` |
| `circuit3name` | `H3` |
| `circuit4name` | `H4` |
| `circuit5name` | `H5` |
| `circuit6name` | `H6` |
| `circuit7name` | `H7` |
| `systembackgroundcolorcircuit1` | `1` |
| `systembackgroundcolorcircuit2` | `0` |
| `systembackgroundcolorcircuit3` | `1` |
| `systembackgroundcolorcircuit4` | `1` |
| `systembackgroundcolorcircuit5` | `1` |
| `systembackgroundcolorcircuit6` | `1` |
| `systembackgroundcolorcircuit7` | `1` |
| `systembackgroundcolorcwu` | `4` |

## Ballon tampon (bufor*) (18)

| Slug | Valeur actuelle |
|---|---|
| `buforcalcsettemp` | `60.0` |
| `buforcoolinghist` | `2` |
| `buforcoolingtemp` | `10` |
| `buforharmonogramset` | `1` |
| `buformaxsetpoint` | `0` |
| `buformaxsetpointcooling` | `0` |
| `buformaxtemp` | `90` |
| `buformaxtemphist` | `5` |
| `buforminsetpoint` | `0` |
| `buforminsetpointcooling` | `0` |
| `buforsettempdownhist` | `8` |
| `buforsettings` | `1197` |
| `buforstate` | `3209` |
| `bufortempkeepingwarm` | `40` |
| `bufortempstarthydraulic` | `21` |
| `bufortempstarthydrauliccooling` | `15` |
| `bufortempstarthydrauliccoolinghist` | `2` |
| `bufortempstarthydraulichist` | `2` |

## Source de chaleur (heatsource*) (27)

| Slug | Valeur actuelle |
|---|---|
| `heatsourceaddtype` | `0` |
| `heatsourcecalcpresettemp` | `65` |
| `heatsourcecontactsett` | `1` |
| `heatsourcecontactstarthyst` | `5` |
| `heatsourcecontactstate` | `64` |
| `heatsourcecontactstophyst` | `3` |
| `heatsourcecoolingaddtemp` | `90` |
| `heatsourcecoolinghyst` | `5` |
| `heatsourcecoolingmaintemp` | `90` |
| `heatsourcecoolingsett` | `3` |
| `heatsourcecoolingstate` | `0` |
| `heatsourcemainpumpext` | `3` |
| `heatsourcemainpumpoverruntime` | `0` |
| `heatsourcemainpumpsett` | `8` |
| `heatsourcemainpumpstate` | `0` |
| `heatsourcemaintype` | `32768` |
| `heatsourcemaxpresettemp` | `80` |
| `heatsourceminpresettemp` | `40` |
| `heatsourceminsupplyhisttemp` | `2` |
| `heatsourceminsupplystate` | `1` |
| `heatsourceminsupplytemp` | `20` |
| `heatsourcepresettemp` | `60` |
| `heatsourcepresettempsett` | `2` |
| `heatsourcepresettempstate` | `0` |
| `heatsourcetempinc` | `5` |
| `heatsourcetempincbuffer` | `2` |
| `heatsourcetype` | `0` |

## Mixeurs (mixerN / mixNpid / mixcirc) (40)

| Slug | Valeur actuelle |
|---|---|
| `mix1pidkp` | `3.0` |
| `mix1pidti` | `160.0` |
| `mix2pidkp` | `3.0` |
| `mix2pidti` | `160.0` |
| `mix3pidkp` | `3.0` |
| `mix3pidti` | `160.0` |
| `mix4pidkp` | `3.0` |
| `mix4pidti` | `160.0` |
| `mix5pidkp` | `3.0` |
| `mix5pidti` | `160.0` |
| `mix6pidkp` | `3.0` |
| `mix6pidti` | `160.0` |
| `mix7pidkp` | `3.0` |
| `mix7pidti` | `160.0` |
| `mixcirc1heatcurvefancoil` | `0.7` |
| `mixcirc2heatcurvefancoil` | `0.7` |
| `mixcirc3heatcurvefancoil` | `0.7` |
| `mixcirc4heatcurvefancoil` | `0.7` |
| `mixcirc5heatcurvefancoil` | `0.7` |
| `mixcirc6heatcurvefancoil` | `0.7` |
| `mixcirc7heatcurvefancoil` | `0.7` |
| `mixer1valvesetposition` | `0` |
| `mixer2valvedeadzone` | `1.0` |
| `mixer2valveopeningtime` | `120` |
| `mixer2valvesetposition` | `0` |
| `mixer3valvedeadzone` | `1.0` |
| `mixer3valveopeningtime` | `120` |
| `mixer3valvesetposition` | `0` |
| `mixer4valvedeadzone` | `1.0` |
| `mixer4valveopeningtime` | `120` |
| `mixer4valvesetposition` | `0` |
| `mixer5valvedeadzone` | `1.0` |
| `mixer5valveopeningtime` | `120` |
| `mixer5valvesetposition` | `0` |
| `mixer6valvedeadzone` | `1.0` |
| `mixer6valveopeningtime` | `120` |
| `mixer6valvesetposition` | `0` |
| `mixer7valvedeadzone` | `1.0` |
| `mixer7valveopeningtime` | `120` |
| `mixer7valvesetposition` | `0` |

## ECS / anti-légionellose (hdw*) (16)

| Slug | Valeur actuelle |
|---|---|
| `hdwdbstate` | `2` |
| `hdwharmonogramsettings` | `1` |
| `hdwheatsource` | `2` |
| `hdwlegionday` | `0` |
| `hdwlegionhour` | `2` |
| `hdwlegionsetpoint` | `70` |
| `hdwloadtime` | `0` |
| `hdwmaxtemphist` | `2` |
| `hdwminmalhisteresis` | `0` |
| `hdwsetpointcalculate` | `45` |
| `hdwsettings` | `265395` |
| `hdwstartlegion` | `0` |
| `hdwstate` | `192` |
| `hdwsupplyhist` | `5` |
| `hdwtempkeepwarm` | `30` |
| `hdwtsetpointdownhist` | `5` |

## Circulation ECS (circulation*) (7)

| Slug | Valeur actuelle |
|---|---|
| `circulationharmonogramsettings` | `1` |
| `circulationhisttemp` | `2` |
| `circulationsettings` | `5` |
| `circulationstate` | `2` |
| `circulationtempstart` | `30` |
| `circulationtimestop` | `10` |
| `circulationtimework` | `20` |

## Réseau / WiFi / IP (16)

| Slug | Valeur actuelle |
|---|---|
| `adres_ip` | `0` |
| `adres_ip_wifi` | `0` |
| `brama_ip` | `0` |
| `brama_ip_wifi` | `0` |
| `gwifi` | `0.0.0.0` |
| `haslo_wifi` | `` |
| `iplan` | `0.0.0.0` |
| `ipwifi` | `0.0.0.0` |
| `maska_ip` | `0` |
| `maska_ip_wifi` | `0` |
| `mwifi` | `0.0.0.0` |
| `sila_sygnalu_wifi` | `0` |
| `status_ip` | `0` |
| `status_wifi` | `0` |
| `szyfrowanie_wifi` | `4` |
| `szyfwifi` | `WPA2` |

## Alarmes & bits de diagnostic (10)

| Slug | Valeur actuelle |
|---|---|
| `alarmbits_1` | `0` |
| `alarmbits_2` | `0` |
| `alarmbits_3` | `0` |
| `alarmbits_4` | `0` |
| `alarmbits_5` | `0` |
| `detectalarmsettings` | `65280` |
| `detectalarmstate` | `16711680` |
| `workstate2` | `2` |
| `workstate3` | `37449` |
| `workstate4` | `0` |

## Non catégorisés (44)

| Slug | Valeur actuelle |
|---|---|
| `allowworkweathertempsett` | `0` |
| `allowworkweathertempstate` | `0` |
| `analog_boiler_control_control` | `0.0` |
| `analog_boiler_control_settings` | `0` |
| `analog_boiler_control_state` | `0` |
| `antifreezetemp` | `5` |
| `buffersettemp` | `60` |
| `circuit1_romtempset` | `0.0` |
| `circuit1maxsetpointcooling` | `23` |
| `circuit1minsetpointcooling` | `16` |
| `circuit2_romtempset` | `15.0` |
| `circuit2maxsetpointcooling` | `23` |
| `circuit2minsetpointcooling` | `16` |
| `circuit3_romtempset` | `0.0` |
| `circuit3maxsetpointcooling` | `23` |
| `circuit3minsetpointcooling` | `16` |
| `circuit4_romtempset` | `0.0` |
| `circuit4maxsetpointcooling` | `23` |
| `circuit4minsetpointcooling` | `16` |
| `circuit5_romtempset` | `0.0` |
| `circuit5maxsetpointcooling` | `23` |
| `circuit5minsetpointcooling` | `16` |
| `circuit6_romtempset` | `0.0` |
| `circuit6maxsetpointcooling` | `23` |
| `circuit6minsetpointcooling` | `16` |
| `circuit7_romtempset` | `0.0` |
| `circuit7maxsetpointcooling` | `23` |
| `circuit7minsetpointcooling` | `16` |
| `counterminwork` | `255` |
| `countminworktime` | `255` |
| `currentsourcework` | `1` |
| `decreasesettemp` | `1` |
| `dhw_mode` | `0` |
| `dhwsettemp` | `0` |
| `heaterpumpdecreaseforbuffer` | `5` |
| `heaterpumpdecreasefordhw` | `5` |
| `highcircuittemp` | `0` |
| `minworktime` | `12` |
| `periodicworktime` | `0` |
| `sourcetempatstart` | `nan` |
| `temppowgz` | `0.0` |
| `tempsettings` | `1` |
| `uid` | `1M86DIP6H1GQE1H6P3KGIH5` |
| `worktime` | `0` |
