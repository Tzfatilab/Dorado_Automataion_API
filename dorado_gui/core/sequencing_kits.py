"""Dorado demultiplexing kit choices verified against the official CLI reference.

Source (checked 2026-10-05):
https://software-docs.nanoporetech.com/dorado/latest/barcoding/barcoding/#cli-reference
These are Dorado IDs (hyphens), not catalog product codes (sometimes dots).
Support depends on the installed Dorado version; no runtime download is needed.
"""

DORADO_KITS = tuple("""
EXP-NBD103 EXP-NBD104 EXP-NBD114 EXP-NBD114-24 EXP-NBD196 EXP-PBC001
EXP-PBC096 SQK-16S024 SQK-16S114-24 SQK-DRB004-24 SQK-HTB114-96 SQK-LWB001
SQK-MAB114-24 SQK-MLK111-96-XL SQK-MLK114-96-XL SQK-NBD111-24 SQK-NBD111-96
SQK-NBD114-24 SQK-NBD114-96 SQK-PBK004 SQK-PCB109 SQK-PCB110 SQK-PCB111-24
SQK-PCB114-24 SQK-RAB201 SQK-RAB204 SQK-RBK001 SQK-RBK004 SQK-RBK110-96
SQK-RBK111-24 SQK-RBK111-96 SQK-RBK114-24 SQK-RBK114-96 SQK-RLB001 SQK-RPB004
SQK-RPB114-24 TWIST-16-UDI TWIST-96A-UDI VSK-PTC001 VSK-VMK001 VSK-VMK004 VSK-VPS001
""".split())
