"""Sample data shaped like the real sources."""

TRVE_BASE_CSV = """DATE_DEBUT;DATE_FIN;P_SOUSCRITE;PART_FIXE_HT;PART_FIXE_TTC;PART_VARIABLE_HT;PART_VARIABLE_TTC
01/02/2025;31/07/2025;6;141,12;180,72;0,1269;0,2016
01/08/2025;31/01/2026;6;146,04;186,24;0,1265;0,1952
01/02/2026;;6;150,00;191,52;0,1300;0,1940
01/02/2026;;9;180,00;232,08;0,1300;0,1940
;;;;;;
"""

TRVE_HPHC_CSV = """DATE_DEBUT;DATE_FIN;P_SOUSCRITE;PART_FIXE_HT;PART_FIXE_TTC;PART_VARIABLE_HC_HT;PART_VARIABLE_HC_TTC;PART_VARIABLE_HP_HT;PART_VARIABLE_HP_TTC
01/08/2025;31/01/2026;6;150,00;196,68;0,1000;0,1635;0,1300;0,2081
01/02/2026;;6;155,00;201,48;0,1010;0,1620;0,1320;0,2068
"""

PRVG_HTML = """<html><body>
<h2>Prix repère de vente de gaz naturel pour le mois d'octobre 2026</h2>
<table>
<tr><th></th><th colspan="2">Cuisson/eau chaude</th><th colspan="2">Chauffage</th></tr>
<tr><th></th><th>HT</th><th>TTC</th><th>HT</th><th>TTC</th></tr>
<tr><td>Abonnement (€/an)</td><td>110,00</td><td>149,80</td><td>250,00</td><td>357,10</td></tr>
<tr><td>Prix par kWh moyen (€/kWh)</td><td>0,14000</td><td>0,18800</td><td>0,11300</td><td>0,15500</td></tr>
<tr><td>Prix par kWh fourchette basse</td><td>0,13800</td><td>0,18560</td><td>0,10665</td><td>0,14798</td></tr>
</table>
<h2>Prix repère pour le mois de novembre 2026</h2>
<table>
<tr><th></th><th colspan="2">Cuisson/eau chaude</th><th colspan="2">Chauffage</th></tr>
<tr><th></th><th>HT</th><th>TTC</th><th>HT</th><th>TTC</th></tr>
<tr><td>Abonnement (€/an)</td><td>112,84</td><td>152,46</td><td>252,04</td><td>360,79</td></tr>
<tr><td>Prix par kWh moyen (€/kWh)</td><td>0,14190</td><td>0,19027</td><td>0,11467</td><td>0,15760</td></tr>
</table>
</body></html>"""

DATASET_JSON = {
    "resources": [
        {
            "title": "Option Base",
            "format": "csv",
            "url": "https://example.test/base.csv",
            "last_modified": "2026-02-01",
        },
        {
            "title": "Option HPHC",
            "format": "csv",
            "url": "https://example.test/hphc.csv",
            "last_modified": "2026-02-01",
        },
        {
            "title": "Option Tempo",
            "format": "csv",
            "url": "https://example.test/tempo.csv",
            "last_modified": "2026-02-01",
        },
    ]
}
