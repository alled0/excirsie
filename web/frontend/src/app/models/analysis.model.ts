export interface AnalysisResult {
  success: boolean;
  exerciseKey: string;
  exerciseName: string;
  repsTotal: number;
  repsLeft?: number;
  repsRight?: number;
  signalQuality: number;
  dropoutRate: number;
  meanReliability: number;
  unknownRate: number;
  abortedReps: number;
  rejectedReps: number;
  framesTotal: number;
  framesDetected: number;
  fpsMean: number;
}
