# ComputerCraft / CC: Tweaked Project

Welcome to my collection of ComputerCraft scripts and utilities! This repository contains various programs for managing displays, audio, and automation.

## ⚠️ Status & Stability

* **`image_to_monitor` & `speakers`:** These are the **only officially working and polished** modules in this repository. They are fully tested and ready for regular use.
* **Other files:** The rest of the scripts and folders in this repository will *likely* work, but they are considered experimental, unpolished, and may require manual tweaking.

---

## 📁 Project Structure & Requirements

To run most of the files in this repository successfully, your ComputerCraft computer **must have a `.apis` folder** located in its root directory containing all the required API files.

Your in-game folder structure should look similar to this:
```text
/
├── .apis/
│   ├── displaymanager.lua (and any other required API files)
│   └── ...
├── startup.lua
└── speakers.lua