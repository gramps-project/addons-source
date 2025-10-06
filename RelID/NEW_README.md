# Gramps - Relations Tab

**Genealogical Relationship Analysis Tool for Gramps**

---
## Description

**Relations Tab** is a module for [Gramps](https://gramps-project.org/), the free and open-source genealogy software. It allows users to visualize, analyze, and export relationships between individuals in a genealogical database, calculating advanced metrics such as relationship distance, Kekulé number, family centrality, and more.

---
## Features

### Relationship Metrics
- **Relationship Distance**: Calculates the generational distance between two individuals.
- **Kekulé Number**: Identifies the type of relationship (cousin, uncle, etc.) using Kekulé notation.
- **Most Recent Ancestor (MRA)**: Calculates the most recent common ancestor and their position.
- **Family Centrality**: Measures the importance of an individual in the family network (number of descendants, ancestors, unions).
- **Surname Diversity**: Ratio of surname diversity over a given number of generations.

### Filters and Visualization
- **Customizable Filters**: Ancestors, descendants, or specific relationships.
- **GTK Interface**: Interactive table with sorting and data export.
- **ODS Export**: Saves results to a spreadsheet (OpenDocument format).

### Advanced Options
- **Network Metrics**: Toggle for advanced calculations (shared subtree, centrality, etc.).
- **Generation Depth**: Limits the number of generations to analyze.

---
## Requirements

- **Gramps** (version 6.0 or later)
- **Python 3.8+**
- **Python Libraries**:
  - `gi` (for GTK)
  - `logging`, `functools`, `collections`, `os`, `time`, `re`, `hashlib`
- **Gramps API**: Access to Gramps internal modules (`gramps.gen.*`, `gramps.gui.*`).

---
## Installation

1. Clone the repository (if available) or copy the `relation_tab.py` file to the Gramps plugins directory:
   ```bash
   mkdir -p ~/.gramps/gramps60/plugins/RelationTab
   cp relation_tab.py ~/.gramps/gramps60/plugins/RelationTab/
   ```
2. Restart Gramps: The module will appear in the Tools menu.

---
## Usage

### Launching
1. Open Gramps and load a database.
2. Go to **Tools > Analysis and Exploration > Relations Tab**.

### Interface
- **Results Table**: Displays metrics for each individual related to the root person.
- **Buttons**:
  - **Save**: Exports results to ODS.
  - **Quit**: Closes the tool.

### Options
- **Generation Depth**: Limits the number of generations analyzed.
- **Network Metrics**: Enables/disables advanced calculations (centrality, surname diversity, etc.).

---
## Example Output

```plaintext
Kekulé ID  | Relationship       | Name                     | Ga   | Gb   | MRA  | Rank  | Period
-----------------------------------------------------------------------------------------------------------
12         | First Cousin       | John DOE                 | 3    | 3    | 7    | 4     | 1850-1920
15         | Uncle              | Peter SMITH              | 2    | 1    | 3    | 2     | 1820-1890
...
```

---
## Development

### Code Structure
- **`FamilyPathMetrics`**: Static class for metric calculations.
- **`RelationFilterManager`**: Manages filter creation and application.
- **`RelationTab`**: Main class for interface and logic.
- **`TableReport`**: Handles ODS data export.

### Testing
- **`test_family_path_metrics()`**: Validates core calculations (MRA, Kekulé, etc.).
- **Logs**: Errors and info are logged to `debug.log`.

---
## Contribution

- **Report a Bug**: Open an issue on the repository (if available).
- **Suggest an Improvement**: Fork the project and submit a pull request.

---
## License

This module is distributed under the **GNU GPL v2+** license. See the `LICENSE` file for details.

---
## Acknowledgments

Thanks to the Gramps community for their ongoing work on this free and open-source software.
