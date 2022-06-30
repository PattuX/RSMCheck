# RSMCheck Quick Start

## Installation

Python3 with pip is required.

In your command line, navigate to ```RSMCheck/src``` and run

```pip3 install -r requirements.txt```

## Usage

### Running the checker

To run the checker from the ```src``` folder simply run

```python3 rsmcheck.py path/to/rsm/file path/to/ctl/file```

For your first run, you can check the example RSM of Figure 2 in the paper against the CTL formulas we use to explain the algorithms (see the example CTL file) by running ```python3 rsmcheck.py ../models/example.rsm ../models/example.ctl ``` from ```src```. Since the example is rather small, you can also check other formulas and confirm the correctness of our program by checking the formula on the RSM by hand.

The result will be printed on the command line, as well as logged in the ```log.log``` file that will be created in the ```src``` directory, along with some additional statistics, such as contexts built and runtime.

By adding the ```-witness``` flag a witness path is generated and saved to ```witness.log```.  Note that this is only available for existential formulas which evaluate to ```true```.

By default the lazy approach using GetNextExpansion and FindReason (see the paper for details) is used, but you can add the ```-exhaustive``` flag to force using the exhaustive approach, or the ```-expansion_heuristic``` flag to specify another expansion heuristic. Currently, three heuristics are supported. The default behaviour ```lazy``` uses the GetNextExpansion heuristic, ```random``` chooses a random contextualizable box in each step, and ```all``` corresponds to the ternary expansion heuristic in the evaluation section of the paper, i.e., is the heuristic that unpacks all contextualizable boxes.

For more options, type ```python3 rsmcheck.py -h```. Note that the memory limit option is only available for UNIX-systems.

### Input format

Here, we specify how you can define your own CTL formulas and RSMs such that our tool can check them. If you only want to run our tool on the examples we included or on randomly generated examples you can skip this section.

#### CTL

A CTL file is expected to contain one or more CTL formulas.  Each line must contain a CTL formula with the standard quantifiers ```A``` and ```E```, path operators ```G```, ```F```, ```U```, boolean operators ```not```, ```~```, ```and```/```&```, ```or```/```|``` and ```-->```,  and constant values ```true``` and ```false```, e.g., ```A(true U (q or not E X p))```. Note that each operator must be surrounded by either parentheses or spaces. Further details can be found in the [pyModelChecking documentation](https://pymodelchecking.readthedocs.io/en/latest/logics_API.html#id2).

#### RSM

RSMs are represented by [JSON](https://www.json.org/json-en.html) format files. The name of each object (node, box, component) must be unique. Objects are always referenced by their ```name``` attribute.

The RSM object is represented like this:

<pre>{ 
"initial_component" : "c1", 
"initial_node" : "n11", 
"components": [ ComponentObject, ... ] 
}</pre>
Note that in contrast to the paper we only allow one initial state. However, a model-checking instance of a CTL formula ```phi``` over an RSM ```A```with multiple initial states can easily be translated to the single-initial-state case by adding a component containing the following:

* one initial node
* one box, referencing the initial component of ```A```
* the same exit nodes as the initial component of ```A``` with the same labels

The initial node is then connected to all call nodes of the box and each return node is connected to the corresponding exit node. Checking this extended RSM for ```A X phi``` then gives the same result as checking ```A``` for ```phi```.

Each component object has the following form:

<pre>{
	"name": "c1",
    "nodes": [
        NodeObject, ...
    ],
    "boxes": [
        BoxObject, ...
    ]
    "transitions": [
        {
            "source": {
                NodeRefObject
            },
            "targets": [
                NodeRefObject, ...
            ]
        },
        ...
    ]
}</pre>

Each box is represented by e.g. ```{ "name": "b11", "component": "c2", "call_nodes": [ "n21", ... ], "return_nodes": [ "n22", ...  ] }```where ```call_nodes``` and ```return_nodes``` must contain a subset of the call and exit nodes of ```component```, respectively.

Each node object is represented by e.g. ```{"name": "n11", is_entry": true, "is_exit": false, "labels": [ "a", ...] }```.

A NodeRef object only gives the name and type of the referenced node or box node, i.e.```{"node": "n1", "type": "node"}```or```{"node_name": "n22","box_name": "b11","type": "box_node"}```, respectively.



### Scripts

Along with the main program, we also provide a few helpful scripts for automated checking and example generation and conversion.

All scripts are located in ```src/etc``` but many must be run from the ```src``` directory in order for Python to correctly import RSM functionalities.

##### mass_check.py

call by ```python3 etc/mass_check.py path/to/directory``` 

Wrapper for multiple ``` rsmcheck.py```  calls. Given a directory, it checks all RSMs in the directory against a ```all.ctl``` file that must be contained in the same directory.

##### random_rsm.py

call by ```python3 etc/random_rsm.py <RSM parameters> -out ../models/random.rsm```

Construct a random RSM with the given parameters and save if to a file. The transitions of the RSM are considered separately to either exist or not, i.e., connectedness is not guaranteed, especially for RSMs with low transition density and/or few nodes.

To see the full list of parameters that must be specified, call  ```python3 etc/random_rsm.py -h```.

##### random_ctl.py

call by ```python3 etc/random_ctl.py <CTL parameters> -out ../models/random.ctl``` 

Construct a random CTL with the given parameters and save if to a file.

To see the full list of parameters that must be specified, call  ```python3 etc/random_ctl.py -h```.

##### jimple_convert.py

call by ```python3 etc/jimple_convert.py path/to/pdmu``` 

Convert a ``` .pdmu``` file generated by JimpleToPDSolver to a ``` .pds``` file compatible with PuMoC, a ``` .rsm``` file compatible with RSMCheck, and a ``` .ctl``` file. This script is rather fragile and probably does not work on ``` .pdmu``` files generated by other means.

##### pds_to_rsm.py

call by ```python3 etc/pds_to_rsm.py path/to/pds/file``` 

Converts a ``` .pds``` file as specified by PuMoC into an ``` .rsm``` file.

##### mass_convert_pds.py

call by ```python3 etc/mass_convert_pds.py path/to/pds/directory path/to/output/rsm/files``` 

Wrapper for multiple ``` pds_to_rsm.py``` calls. Given a directory, convert all PuMoC ``` .pds``` files to ``` .rsm``` riles and write them to another directory.

##### mass_convert_ctl.py

call by ```python3 etc/mass_convert_ctl.py path/to/pumoc/ctl/files path/to/output/rsmcheck/ctl/files``` 

Given a directory, it converts all CTL files from the PuMoC format to the RSMCheck format. This is purely syntactical, e.g. replacing ```&&``` by ```&``` and adding spaces required for correct parsing.

## Reproducing our results

### 50x50 random

In the paper we compare the exhaustive to the lazy approach by evaluating both on 50 random RSMs, each checked against 50 random CTLs generated by the scripts ```random_rsm.py``` and ```random_ctl.py```. Our generated RSMs and CTLs can be found in ```models/random```. 

Specifically, the ```i```-th RSM contains ```i``` components, each containing ```⌊i/3⌋``` boxes and ```3i``` nodes of which approximately 5% are entry nodes and another 5% are exit nodes with each component being guaranteed at least one entry and exit node. The labels ```a```, ```b``` and ```c``` are attached to approximately 40%, 60% and 50% of all nodes, respectively. The connectivity density in each component is around 20%. 
The  formulas are defined over ```{a,b,c}``` using existential quantifiers and the ```j```-th formula has a quantifier depth of ```⌊j/9⌋``` and a branching factor of 2 for conjunctions and disjunctions, where each subformula has a 50% chance of being negated.

The checking process for a single instance of the 50x50 grid can then be invoked as described at the beginning of the Usage section by running the checker and grabbing the run times from the log file. Alternatively, you can run all 2500 model checking instances by calling the ```mass_check.py``` script on the folder ```models/random```.

### 500 PDS

We also compared PuMoC to RSMCheck on [500 random PDSs and CTL formulas that are provided by PuMoC](https://lipn.univ-paris13.fr/~touili/PuMoC/download.html). The PDSs can be converted into RSMs using either ```pds_to_rsm.py``` or ```mass_convert_pds.py```. Similarly, the 500 corresponding CTL files can be converted via ```mass_convert_ctl.py```. Then the RSMs and CTLs are ready to be checked by our tool as above.

We do not include the RSMs to reduce the size of this sample implementation. If you want all 500 RSMs and want to save te time of converting the PDSs yourself, you can request the RSMs directly from us.

### Jimple examples

Lastly, we considered [real world Java examples that are provided by PDSolver](https://www.cs.rhul.ac.uk/home/uxac009/files/implementations/pdsolver_spin.html). The PDMUs can be converted into PDSs and RSMs, along with extracting CTL formulas using ```jimple_convert.py```. The RSMs and CTLs can be found in  ```models/PDMUs```and again be checked as above. The CTL files can then be modified manually to fit the PuMoC format and model checked using the [PuMoC model checker](https://lipn.univ-paris13.fr/~touili/PuMoC/quick%20start.html).

Note that the provided ```avroraISEA``` example does not contain a mu-property, and thus we cannot extract a CTL formula.
