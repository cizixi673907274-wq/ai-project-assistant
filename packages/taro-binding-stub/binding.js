"use strict";

class Creator {
  constructor(templateRoot, destinationRoot) {
    this.templateRoot = templateRoot;
    this.destinationRoot = destinationRoot;
  }

  async createFileFromTemplate() {
    throw new Error("@tarojs/binding native creator is disabled in this workspace build.");
  }
}

const CompilerType = {
  Webpack4: "Webpack4",
  Webpack5: "Webpack5",
  Vite: "Vite",
};

const CSSType = {
  None: "None",
  Sass: "Sass",
  Stylus: "Stylus",
  Less: "Less",
};

const FrameworkType = {
  React: "React",
  Preact: "Preact",
  Vue3: "Vue3",
  Solid: "Solid",
  None: "None",
};

const NpmType = {
  Yarn: "Yarn",
  Cnpm: "Cnpm",
  Pnpm: "Pnpm",
  Npm: "Npm",
};

const PeriodType = {
  CreateAPP: "CreateAPP",
  CreatePage: "CreatePage",
};

async function createPage() {
  throw new Error("@tarojs/binding native page creator is disabled in this workspace build.");
}

async function createPlugin() {
  throw new Error("@tarojs/binding native plugin creator is disabled in this workspace build.");
}

async function createProject() {
  throw new Error("@tarojs/binding native project creator is disabled in this workspace build.");
}

module.exports = {
  Creator,
  CompilerType,
  CSSType,
  FrameworkType,
  NpmType,
  PeriodType,
  createPage,
  createPlugin,
  createProject,
};
