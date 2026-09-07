"use strict";

const MessageKind = {
  Info: 0,
  Error: 1,
  Success: 2,
  Warning: 3,
  Manual: 4,
};

function okResult() {
  return {
    isValid: true,
    messages: [],
  };
}

function pluginDoctor(ctx) {
  if (!ctx || typeof ctx.registerCommand !== "function") return;
  ctx.registerCommand({
    name: "doctor",
    fn() {
      console.log("Taro Doctor native check is disabled for this workspace build.");
    },
  });
}

async function validateConfig() {
  return okResult();
}

async function validateConfigPrint() {
  return true;
}

function validateEnv() {
  return okResult();
}

function validateEnvPrint() {
  return true;
}

function validatePackage() {
  return okResult();
}

function validatePackagePrint() {
  return true;
}

function validateRecommend() {
  return okResult();
}

function validateRecommendPrint() {
  return true;
}

async function validateEslint() {
  return okResult();
}

async function validateEslintPrint() {
  return true;
}

module.exports = pluginDoctor;
module.exports.default = pluginDoctor;
module.exports.MessageKind = MessageKind;
module.exports.validateConfig = validateConfig;
module.exports.validateConfigPrint = validateConfigPrint;
module.exports.validateEnv = validateEnv;
module.exports.validateEnvPrint = validateEnvPrint;
module.exports.validatePackage = validatePackage;
module.exports.validatePackagePrint = validatePackagePrint;
module.exports.validateRecommend = validateRecommend;
module.exports.validateRecommendPrint = validateRecommendPrint;
module.exports.validateEslint = validateEslint;
module.exports.validateEslintPrint = validateEslintPrint;
