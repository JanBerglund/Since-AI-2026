# Evaluation Results

> A tests rule logic on explicitly synthetic data; it does not measure vessel compliance or extraction accuracy.
> B compares human-entered labels from the real PDF page with OCR output and is the real measure of extraction accuracy.

## A: Synthetic rule cases

Dataset: `cases_rules.json` (36 synthetic cases). Expected verdicts are hand-entered from `rules.json` thresholds; the checker is not used to generate them.

| Case | Rule | Expected | Predicted | Match |
| --- | --- | --- | --- | --- |
| D01-clear-fine | door_clear_width | fine | fine | yes |
| D02-wide-fine | door_clear_width | fine | fine | yes |
| D03-exact-threshold | door_clear_width | fine | fine | yes |
| D04-just-below | door_clear_width | not_fine | not_fine | yes |
| D05-clear-violation | door_clear_width | not_fine | not_fine | yes |
| D06-small-violation | door_clear_width | not_fine | not_fine | yes |
| D07-missing-width | door_clear_width | unknown | unknown | yes |
| D08-na-width | door_clear_width | unknown | unknown | yes |
| D09-inch-value-entered-as-mm | door_clear_width | not_fine | not_fine | yes |
| D10-low-confidence-violation | door_clear_width | unknown | unknown | yes |
| D11-low-confidence-fine | door_clear_width | unknown | unknown | yes |
| D12-text-number | door_clear_width | fine | fine | yes |
| D13-confidence-at-floor | door_clear_width | fine | fine | yes |
| D14-below-threshold | door_clear_width | not_fine | not_fine | yes |
| D15-large-fine | door_clear_width | fine | fine | yes |
| C01-clear-fine | corridor_width | fine | fine | yes |
| C02-wide-fine | corridor_width | fine | fine | yes |
| C03-exact-threshold | corridor_width | fine | fine | yes |
| C04-just-below | corridor_width | not_fine | not_fine | yes |
| C05-clear-violation | corridor_width | not_fine | not_fine | yes |
| C06-small-violation | corridor_width | not_fine | not_fine | yes |
| C07-missing-width | corridor_width | unknown | unknown | yes |
| C08-na-width | corridor_width | unknown | unknown | yes |
| C09-inches-in-mm-field | corridor_width | unknown | unknown | yes |
| C10-low-confidence-violation | corridor_width | unknown | unknown | yes |
| C11-low-confidence-fine | corridor_width | unknown | unknown | yes |
| C12-text-number | corridor_width | fine | fine | yes |
| C13-confidence-at-floor | corridor_width | not_fine | not_fine | yes |
| C14-low-confidence-at-threshold | corridor_width | unknown | unknown | yes |
| C15-large-fine | corridor_width | fine | fine | yes |
| P01-waste-oil-sludge-found | marpol_annex1_oil_residue_tank_shown | fine | fine | yes |
| P02-sewage-sludge-excluded | marpol_annex1_oil_residue_tank_shown | unknown | unknown | yes |
| P03-garbled-sludge-tank | marpol_annex1_oil_residue_tank_shown | fine | fine | yes |
| P04-label-on-unselected-page | marpol_annex1_oil_residue_tank_shown | unknown | unknown | yes |
| P05-tonnage-unknown | marpol_annex1_oil_residue_tank_shown | unknown | unknown | yes |
| P06-below-400-gt | marpol_annex1_oil_residue_tank_shown | not_applicable | not_applicable | yes |

| Metric | Count |
| --- | ---: |
| Caught violations (expected and predicted `not_fine`) | 9 |
| Missed violations (expected `not_fine`, predicted `fine`; dangerous error) | **0** |
| False alarms (expected `fine`, predicted `not_fine`) | 0 |
| Unknowns (abstentions) | 13 |
| Not applicable | 1 |
| All expected/predicted mismatches | 0 |

## B: Real page-12 OCR check

Source PDF: `C:\Users\janbe\Downloads\6096-070-001-(J) General Arrangement.pdf`  
Page: 12  
Human labels filled: 0/15  
OCR labels extracted: 477  
Fuzzy text-match threshold: 0.70 similarity (normalized exact matches are checked first).

No human ground-truth labels have been entered yet. Per-label accuracy is therefore not scored; fill `text` in `page12_ground_truth.json` by reading the drawing, then rerun this script.

### OCR output (machine labels, not ground truth)

These are the page-12 labels emitted by `backend/ocr_labels.py`; they must not be treated as human transcription.

| OCR label | Confidence |
| --- | ---: |
| —— 1 -1-+ | 0.243 |
| a | 0.430 |
| —/ | 0.410 |
| sy LF | 0.145 |
| AFT PEAK | 0.580 |
| _ | 0.200 |
| AFT PEAK | 0.935 |
| VOID P | 0.880 |
| _3-88-1 | 0.250 |
| VOID S | 0.870 |
| 3-88-2 gi | 0.685 |
| \ VOID | 0.845 |
| 3588-0 | 0.410 |
| i | 0.390 |
| wh | 0.510 |
| an | 0.960 |
| 90 | 0.920 |
| IQ | 0.640 |
| + | 0.620 |
| Sin | 0.040 |
| d a) ately | 0.363 |
| nn an | 0.300 |
| ae | 0.200 |
| a | 0.250 |
| iv | 0.330 |
| REPAIR PAR | 0.505 |
| Wa | 0.590 |
| va | 0.320 |
| OTOR/DRIVE | 0.840 |
| pw | 0.280 |
| pH | 0.020 |
| 3-77-0 | 0.910 |
| ROOM | 0.960 |
| HYDRAULIC | 0.660 |
| 3-85-1 | 0.840 |
| att | 0.470 |
| = | 0.850 |
| ie) | 0.440 |
| sEirts | 0.000 |
| 77-1 | 0.150 |
| 7 | 0.540 |
| THRUSTER | 0.910 |
| 3-85-2 | 0.580 |
| ip | 0.680 |
| 0 | 0.850 |
| fe} | 0.290 |
| TA\ | 0.810 |
| A\ K | 0.800 |
| A | 0.890 |
| SEACHEST | 0.920 |
| \ | 0.860 |
| / \ | 0.765 |
| 807 | 0.590 |
| @ 4. | 0.260 |
| @) | 0.060 |
| 4-67-2 | 0.730 |
| O1b | 0.050 |
| 77 | 0.830 |
| 1 | 0.430 |
| \ | 0.560 |
| + | 0.750 |
| MITWT | 0.470 |
| 1 | 0.410 |
| BHD | 0.960 |
| BHD | 0.950 |
| WT | 0.710 |
| SJE | 0.580 |
| SW 4 | 0.000 |
| Fee) | 0.340 |
| 5 | 0.620 |
| aa | 0.480 |
| om | 0.450 |
| ——rtL.., | 0.000 |
| FUEL OIL _7P | 0.760 |
| FUEL | 0.870 |
| SCIENCE STORES | 0.930 |
| Di))) | 0.000 |
| -4-67— | 0.440 |
| N | 0.000 |
| i | 0.520 |
| 4-67-2 | 0.810 |
| ‘BALLAST._7S | 0.000 |
| WINGH 00M | 0.405 |
| BALLAST 7P | 0.770 |
| N | 0.550 |
| _ 4-67-4 | 0.070 |
| 4-67-3 | 0.880 |
| 367-2 | 0.320 |
| 3-67-0 | 0.640 |
| <7S | 0.230 |
| i | 0.070 |
| ER ACCESS | 0.960 |
| =s | 0.680 |
| SEACHEST | 0.920 |
| ie} | 0.440 |
| 3-59-2 | 0.620 |
| 4-63-2 | 0.550 |
| SEACHEST ~ | 0.905 |
| = | 0.950 |
| t | 0.150 |
| 4-61- | 0.900 |
| MTW | 0.860 |
| MTWT | 0.580 |
| BHD | 0.960 |
| BHD | 0.960 |
| Ds | 0.500 |
| } | 0.550 |
| ye | 0.360 |
| <= | 0.720 |
| 3-63-0 | 0.760 |
| ECR | 0.960 |
| ue UP | 0.920 |
| 65 | 0.800 |
| l w/c | 0.615 |
| 3-65-1 J, | 0.700 |
| —_— vA | 0.235 |
| aN | 0.300 |
| \v | 0.000 |
| Po | 0.090 |
| ELECTRICAL _ROOM | 0.000 |
| ~~ | 0.170 |
| ~— | 0.130 |
| t | 0.000 |
| a | 0.100 |
| 3-51+1 | 0.240 |
| - | 0.510 |
| ever of es | 0.363 |
| 60. | 0.760 |
| FUEL | 0.350 |
| is c | 0.165 |
| r I | 0.400 |
| ~ | 0.010 |
| HOLDING TANK | 0.910 |
| BALLAST 6B | 0.385 |
| BALLAST. 6S | 0.630 |
| ENGINE | 0.880 |
| 451-2. | 0.460 |
| 4-51- | 0.690 |
| TREATED FW | 0.830 |
| 4-51-6 | 0.700 |
| 4-51-3 | 0.860 |
| OIL 6P~ | 0.330 |
| 3-51-0 | 0.850 |
| a | 0.170 |
| T | 0.000 |
| r | 0.000 |
| 451-4 | 0.310 |
| ROOM | 0.960 |
| T | 0.080 |
| ia | 0.500 |
| - | 0.310 |
| + | 0.810 |
| ® | 0.470 |
| ¥ | 0.100 |
| = | 0.740 |
| _ | 0.340 |
| ae | 0.270 |
| SEWAGE SLUDGE TANK- \| | 0.705 |
| _— | 0.000 |
| T | 0.100 |
| ia | 0.530 |
| - | 0.210 |
| Tv | 0.070 |
| A | 0.240 |
| is | 0.270 |
| r | 0.000 |
| MIWT | 0.890 |
| MTWT | 0.810 |
| BHD | 0.960 |
| BHD | 0.950 |
| ") AUXILIARY | 0.465 |
| ae | 0.210 |
| \| MACHINERY | 0.840 |
| qd | 0.570 |
| d | 0.590 |
| q | 0.440 |
| FO DAY TANK> | 0.807 |
| FO DAY TANK~ | 0.720 |
| t | 0.650 |
| FO SETTLER | 0.550 |
| CENTERBOARD TRUNK | 0.890 |
| 50 | 0.840 |
| HOLD & 1ST PLATFORM | 0.925 |
| _A-47-0 | 0.000 |
| D | 0.780 |
| EQUIPMENT | 0.960 |
| ~ | 0.660 |
| 3-41-4 | 0.470 |
| ROOM | 0.960 |
| “GREY _WATER HOLDING | 0.267 |
| 2 | 0.520 |
| 345-4 \ \| | 0.540 |
| CHILLER | 0.960 |
| - | 0.070 |
| ~FUEL_OIL_5S | 0.000 |
| U=TUBE ROLL TANK ABOVE | 0.868 |
| 2 | 0.430 |
| 2 | 0.110 |
| ROOM | 0.960 |
| 3-41- | 0.630 |
| 3-44-2 \| | 0.885 |
| a | 0.000 |
| — | 0.260 |
| a | 0.480 |
| 3-44— | 0.280 |
| BALLS mes) | 0.670 |
| FUEL OIL SP | 0.460 |
| 2 | 0.110 |
| : | 0.110 |
| - 44st | 0.000 |
| PLAN | 0.960 |
| - | 0.000 |
| PLAN | 0.960 |
| i | 0.450 |
| 4-41-3 | 0.860 |
| 4-4-4 | 0.080 |
| A | 0.600 |
| x | 0.000 |
| \| | 0.660 |
| VI | 0.560 |
| \| | 0.610 |
| 441 | 0.460 |
| ie | 0.390 |
| T | 0.710 |
| \| | 0.570 |
| ial | 0.170 |
| “\| | 0.490 |
| Ir | 0.750 |
| 4-41-0 | 0.750 |
| \ | 0.670 |
| \ | 0.670 |
| \| | 0.560 |
| oe | 0.250 |
| Ne | 0.400 |
| 1/8"=1'-0" | 0.780 |
| 1/8"=1'-0" | 0.390 |
| a | 0.460 |
| TANK TOP | 0.910 |
| 45) | 0.440 |
| S | 0.380 |
| B | 0.000 |
| ~ | 0.900 |
| ars | 0.000 |
| — | 0.050 |
| — | 0.860 |
| — CENTERBOARD TRUNK | 0.630 |
| Tt | 0.290 |
| 10=SC | 0.190 |
| 10-—SA | 0.080 |
| S | 0.000 |
| p-LUBE OIL TANK | 0.627 |
| - | 0.220 |
| 4-41-0 | 0.850 |
| 4-37-0 | 0.650 |
| S | 0.050 |
| - | 0.190 |
| 3-43-2 | 0.420 |
| ii | 0.250 |
| MTWT | 0.680 |
| MTWT | 0.590 |
| p- SEWAGE TANK | 0.643 |
| efi—t—t—4 | 0.000 |
| a | 0.380 |
| BHD | 0.950 |
| BHD | 0.950 |
| 4 | 0.660 |
| d POTABLE | 0.820 |
| 3-41-2 | 0.600 |
| 4 | 0.580 |
| U-TUBE | 0.850 |
| 7S. | 0.360 |
| r | 0.000 |
| U-TUBE | 0.890 |
| OTAB | 0.810 |
| \ ar | 0.650 |
| 4-37-0 | 0.910 |
| \ | 0.900 |
| \ | 0.910 |
| ROLL | 0.960 |
| Th | 0.740 |
| TANK | 0.960 |
| \ | 0.910 |
| \ | 0.390 |
| \- | 0.460 |
| ~37-0 | 0.000 |
| 4-37- | 0.710 |
| ay | 0.460 |
| - | 0.430 |
| ROLL | 0.960 |
| A | 0.910 |
| \ | 0.750 |
| ae | 0.220 |
| \ | 0.810 |
| \| FUEL ‘Oil 4P | 0.588 |
| - | 0.300 |
| 37-1 | 0.580 |
| \ | 0.800 |
| \ | 0.730 |
| \ | 0.880 |
| AN | 0.960 |
| \- | 0.720 |
| + | 0.900 |
| fa | 0.500 |
| \ | 0.780 |
| \ | 0.790 |
| FUELS | 0.000 |
| B | 0.000 |
| DECKS | 0.960 |
| a | 0.000 |
| r | 0.000 |
| 4-33- | 0.750 |
| 4-33-2 | 0.880 |
| BALLAST 45— | 0.350 |
| . | 0.000 |
| BALLAST 4S | 0.580 |
| Li | 0.350 |
| = | 0.130 |
| 1 | 0.400 |
| H | 0.000 |
| \| | 0.930 |
| 1 | 0.500 |
| 1 | 0.430 |
| 1 | 0.420 |
| La | 0.490 |
| La | 0.580 |
| 4-31-3 | 0.840 |
| 4-31-4 | 0.840 |
| £ | 0.000 |
| EQUIPMENT | 0.870 |
| DOMESTIC | 0.950 |
| S | 0.000 |
| 3-31-( | 0.460 |
| a | 0.120 |
| ROOM | 0.960 |
| a | 0.170 |
| - | 0.000 |
| - | 0.300 |
| x | 0.450 |
| uP | 0.820 |
| a | 0.000 |
| ™~ | 0.270 |
| x \_f | 0.125 |
| —' }/ \\ | 0.227 |
| UP | 0.000 |
| MIWT | 0.820 |
| MIWT | 0.800 |
| BHD | 0.960 |
| BHD | 0.960 |
| \| | 0.270 |
| Sy | 0.200 |
| DEF TAN | 0.850 |
| \| | 0.930 |
| A | 0.230 |
| 4-27-0 | 0.840 |
| y~ FUEL OIL OVERFLOW | 0.662 |
| DATA CEN \| ER | 0.755 |
| . | 0.000 |
| 4-31-2 | 0.640 |
| VORKSHOP | 0.890 |
| ~ | 0.890 |
| BALLAST 3P_-—~ | 0.630 |
| BALLAST 3S | 0.690 |
| a | 0.360 |
| ~ | 0.610 |
| Lut | 0.350 |
| OILY WATER | 0.750 |
| 4-31- | 0.750 |
| 2-22-4 | 0.890 |
| _4-22-2 | 0.650 |
| 22- | 0.820 |
| 4-22-1 | 0.780 |
| 1 \| | 0.810 |
| — | 0.470 |
| 4-31-0 | 0.880 |
| WASTE OIL/SLUDGE | 0.580 |
| ; | 0.010 |
| 2-22-2 | 0.860 |
| —— | 0.530 |
| YM | 0.880 |
| Z | 0.000 |
| \| | 0.330 |
| UP | 0.780 |
| Z | 0.000 |
| Va | 0.290 |
| 95 | 0.550 |
| 4 | 0.550 |
| fe) | 0.780 |
| _ | 0.510 |
| ~ | 0.770 |
| Z | 0.000 |
| = | 0.300 |
| fe) | 0.660 |
| MIWT | 0.720 |
| MTWT | 0.690 |
| BHD | 0.950 |
| BHD | 0.960 |
| \| | 0.520 |
| 4 TRANSCEIVER | 0.740 |
| 4 | 0.930 |
| \| ZA, | 0.305 |
| BALLAST Pa | 0.735 |
| BALLAST. o> | 0.485 |
| ROOM | 0.960 |
| a | 0.450 |
| 414-1 | 0.390 |
| 2-18-1 | 0.750 |
| 20 | 0.460 |
| a | 0.000 |
| AFT TRANSDUCER ROOM | 0.473 |
| 4-22-0 | 0.780 |
| g ve | 0.440 |
| STORES | 0.940 |
| 000 | 0.400 |
| SHIP'S | 0.750 |
| 2-14-0 | 0.810 |
| a | 0.420 |
| - | 0.020 |
| 2 | 0.140 |
| p ~~ | 0.095 |
| 5 \ | 0.485 |
| \|S | 0.000 |
| MIWT | 0.840 |
| MIWT | 0.780 |
| BHD | 0.950 |
| BHD | 0.950 |
| FWD TRANSDUCER ROOM | 0.453 |
| 4-14-0 | 0.890 |
| I. | 0.540 |
| Wai | 0.490 |
| (- | 0.000 |
| ga | 0.340 |
| ee | 0.270 |
| sad BOW | 0.470 |
| SEACHEST | 0.920 |
| 4-10-2 | 0.840 |
| l > | 0.520 |
| THRUSTER VOID | 0.940 |
| 4-5-0 | 0.940 |
| BOW THRUSTER ROOM | 0.937 |
| 3-5-0 | 0.910 |
| COLL | 0.960 |
| COLL | 0.950 |
| BHD | 0.900 |
| BHD | 0.930 |
| +} | 0.440 |
| FOREPEAK | 0.910 |
| BALLAST | 0.960 |
| 4-(-4)-0 | 0.760 |
| PROFESSIONAL ENGINEER STAMP. | 0.503 |
| [ FOREPEAK | 0.630 |
| BALLAST | 0.960 |
| 4-(-4)-0 | 0.380 |
| 14 | 0.480 |
| \0 | 0.670 |
| “VOID | 0.550 |
| INSPECTION ACCESS | 0.950 |
| -(-2)- | 0.300 |
| —o | 0.300 |
| SCALE: | 0.960 |
| 199-6" REGIONAL CLASS RESEARCH VESSEL | 0.754 |
| SIZE | 0.960 |
| L) \| 7UTHS | 0.753 |
| OREGON STATE UNIVERSITY | 0.933 |
| PLAN VIEW | 0.935 |
| FSCM CAGE NO. \| DRAWING NO. | 0.928 |
| NONE | 0.960 |
| ARRANGEMENT | 0.960 |
| CORVALLIS, OR 97331 | 0.950 |
| 1ST PLATFORM | 0.730 |
| HULL #:6096 6097 6098 | 0.917 |
| GENERAI | 0.910 |
| — TA | 0.900 |
| 6096-0/0-001 | 0.770 |
| TOP, HOLD & | 0.933 |
| SHEET 10 OF | 0.937 |
| 10 | 0.920 |
| REV | 0.960 |
