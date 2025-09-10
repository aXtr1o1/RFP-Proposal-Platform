"use client";
import React, { useState, useEffect } from 'react';
import { FileText, Zap, Sparkles, CheckCircle } from 'lucide-react';

interface LoadingPageProps {}

const LoadingPage: React.FC<LoadingPageProps> = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);

  const steps = [
    { id: 0, title: "Processing RFP Documents", description: "Analyzing and extracting key information" },
    { id: 1, title: "Uploading to Cloud Storage", description: "Securing your files in Google Drive" },
    { id: 2, title: "Generating Proposal Structure", description: "Creating intelligent proposal framework" },
    { id: 3, title: "Finalizing Configuration", description: "Applying your preferences and settings" }
  ];

  useEffect(() => {
    const stepInterval = setInterval(() => {
      setCurrentStep(prev => {
        if (prev < steps.length - 1) {
          return prev + 1;
        }
        return prev;
      });
    }, 3000);

    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev < 100) {
          return prev + 1;
        }
        return prev;
      });
    }, 120);

    return () => {
      clearInterval(stepInterval);
      clearInterval(progressInterval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-black flex items-center justify-center relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 bg-gradient-to-br from-gray-900 via-black to-gray-900">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,255,255,0.1),transparent)] animate-pulse"></div>
      </div>
      
      {/* Floating particles */}
      <div className="absolute inset-0">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-white rounded-full opacity-30"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 3}s`,
            }}
          >
            <div className="w-1 h-1 bg-white rounded-full animate-ping"></div>
          </div>
        ))}
      </div>

      <div className="max-w-2xl w-full mx-auto px-6 relative z-10">
        {/* Main Loading Card */}
        <div className="bg-gray-900/90 backdrop-blur-xl rounded-3xl shadow-2xl border border-gray-800 overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-gray-800 to-black p-8 text-center relative">
            <div className="relative">
              {/* Animated Icon */}
              <div className="inline-flex items-center justify-center w-24 h-24 bg-white/10 backdrop-blur-sm rounded-full mb-4 border border-white/20">
                <Zap className="text-white animate-pulse" size={40} />
              </div>
              
              {/* Floating Sparkles */}
              <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-2">
                <Sparkles className="text-white animate-bounce" size={20} />
              </div>
              <div className="absolute top-4 right-1/4 transform translate-x-4">
                <Sparkles className="text-gray-300 animate-bounce delay-300" size={16} />
              </div>
              <div className="absolute top-4 left-1/4 transform -translate-x-4">
                <Sparkles className="text-gray-300 animate-bounce delay-700" size={16} />
              </div>
            </div>
            
            <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent mb-2">
              Processing Your RFP
            </h1>
            <p className="text-gray-400 text-lg">
              Please wait while we analyze and process your documents
            </p>
          </div>

          {/* Progress Section */}
          <div className="p-8">
            {/* Progress Bar */}
            <div className="mb-8">
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm font-semibold text-gray-300">Overall Progress</span>
                <span className="text-sm font-bold text-white">{progress}%</span>
              </div>
              <div className="w-full bg-gray-800 rounded-full h-4 overflow-hidden shadow-inner border border-gray-700">
                <div 
                  className="bg-gradient-to-r from-white to-gray-300 h-4 rounded-full transition-all duration-300 ease-out relative overflow-hidden"
                  style={{ width: `${progress}%` }}
                >
                  {/* Animated shine effect */}
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white via-transparent opacity-50 animate-pulse"></div>
                </div>
              </div>
            </div>

            {/* Steps */}
            <div className="space-y-4">
              {steps.map((step, index) => (
                <div 
                  key={step.id}
                  className={`flex items-start gap-4 p-4 rounded-xl transition-all duration-500 border ${
                    index === currentStep 
                      ? 'bg-gray-800/80 border-white/30 shadow-lg backdrop-blur-sm' 
                      : index < currentStep 
                        ? 'bg-gray-800/50 border-green-500/30' 
                        : 'bg-gray-800/30 border-gray-700'
                  }`}
                >
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border transition-all ${
                    index === currentStep 
                      ? 'bg-white text-black border-white animate-pulse' 
                      : index < currentStep 
                        ? 'bg-green-500 text-white border-green-500' 
                        : 'bg-gray-700 text-gray-400 border-gray-600'
                  }`}>
                    {index < currentStep ? (
                      <CheckCircle size={20} />
                    ) : index === currentStep ? (
                      <div className="w-4 h-4 bg-black rounded-full animate-ping"></div>
                    ) : (
                      <FileText size={16} />
                    )}
                  </div>
                  
                  <div className="flex-1">
                    <h3 className={`font-semibold text-lg transition-colors ${
                      index === currentStep 
                        ? 'text-white' 
                        : index < currentStep 
                          ? 'text-green-400' 
                          : 'text-gray-500'
                    }`}>
                      {step.title}
                    </h3>
                    <p className={`text-sm transition-colors ${
                      index === currentStep 
                        ? 'text-gray-300' 
                        : index < currentStep 
                          ? 'text-green-300' 
                          : 'text-gray-600'
                    }`}>
                      {step.description}
                    </p>
                  </div>

                  {/* Loading indicator for current step */}
                  {index === currentStep && (
                    <div className="flex-shrink-0">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Additional Info */}
            <div className="mt-8 p-6 bg-gradient-to-r from-gray-800/50 to-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700">
              <div className="text-center">
                <div className="inline-flex items-center gap-2 text-white font-semibold mb-2">
                  <Sparkles size={20} />
                  AI-Powered Processing
                </div>
                <p className="text-gray-400 text-sm">
                  Our advanced AI is analyzing your documents to create the most effective proposal structure and content recommendations.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Message */}
        <div className="text-center mt-8">
          <p className="text-gray-500">
            This process typically takes 2-5 minutes depending on document complexity
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoadingPage;