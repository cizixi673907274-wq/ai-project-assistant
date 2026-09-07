export enum MessageKind {
  Info = 0,
  Error = 1,
  Success = 2,
  Warning = 3,
  Manual = 4,
}

export interface Message {
  kind: MessageKind;
  content: string;
}

export interface ValidateResult {
  isValid: boolean;
  messages: Message[];
}

declare const pluginDoctor: (ctx: any) => void;
export default pluginDoctor;

export function validateConfig(projectConfig: any, helper: any): Promise<ValidateResult>;
export function validateConfigPrint(projectConfig: any, helper: any): Promise<boolean>;
export function validateEnv(): ValidateResult;
export function validateEnvPrint(): boolean;
export function validatePackage(appPath: string, nodeModulesPath: string): ValidateResult;
export function validatePackagePrint(appPath: string, nodeModulesPath: string): boolean;
export function validateRecommend(appPath: string): ValidateResult;
export function validateRecommendPrint(appPath: string): boolean;
export function validateEslint(projectConfig: any, chalk: any): Promise<ValidateResult>;
export function validateEslintPrint(projectConfig: any, chalk: any): Promise<boolean>;
