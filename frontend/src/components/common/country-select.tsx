"use client"

import React, { useEffect } from "react";
import Select from "react-select";
import { motion } from "framer-motion";
import { Globe } from "lucide-react";

const CountrySelect = ({
  countries,
  setCountries,
  selectedCountry,
  setSelectedCountry
}: {
  countries: Array<any>,
  setCountries: (data: any) => void,
  selectedCountry: any,
  setSelectedCountry: (data: any) => void
}) => {

  useEffect(() => {
    fetch(
      "https://valid.layercode.workers.dev/list/countries?format=select&flags=true&value=code"
    )
      .then((response) => response.json())
      .then((data) => {
        setCountries(data.countries);
        setSelectedCountry(data.userSelectValue);
      }).catch((error) => {
        console.log("Fetching countries error", error);
      });
  }, [setSelectedCountry, setCountries]);

  const customStyles = {
    control: (base: any, state: any) => ({
      ...base,
      minHeight: '56px',
      border: state.isFocused 
        ? '2px solid #3b82f6' 
        : '2px solid #e2e8f0',
      borderRadius: '0.75rem',
      backgroundColor: state.isFocused 
        ? '#f0f9ff' 
        : '#ffffff',
      boxShadow: state.isFocused 
        ? '0 0 0 3px rgba(59, 130, 246, 0.1)' 
        : 'none',
      transition: 'all 0.2s',
      '&:hover': {
        borderColor: '#3b82f6',
      },
    }),
    option: (base: any, state: any) => ({
      ...base,
      backgroundColor: state.isSelected 
        ? '#3b82f6' 
        : state.isFocused 
          ? '#f0f9ff' 
          : 'transparent',
      color: state.isSelected ? 'white' : '#1e293b',
      padding: '12px 16px',
      fontSize: '0.95rem',
      '&:active': {
        backgroundColor: '#3b82f6',
        color: 'white',
      },
    }),
    menu: (base: any) => ({
      ...base,
      borderRadius: '0.75rem',
      boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
      zIndex: 9999,
    }),
    menuList: (base: any) => ({
      ...base,
      borderRadius: '0.75rem',
      padding: '8px',
    }),
    singleValue: (base: any) => ({
      ...base,
      color: '#1e293b',
      fontSize: '0.95rem',
    }),
    placeholder: (base: any) => ({
      ...base,
      color: '#94a3b8',
      fontSize: '0.95rem',
    }),
    dropdownIndicator: (base: any) => ({
      ...base,
      color: '#94a3b8',
      '&:hover': {
        color: '#3b82f6',
      },
    }),
    indicatorSeparator: () => ({
      display: 'none',
    }),
  };

  const darkModeStyles = {
    control: (base: any, state: any) => ({
      ...base,
      minHeight: '56px',
      border: state.isFocused 
        ? '2px solid #60a5fa' 
        : '2px solid #334155',
      borderRadius: '0.75rem',
      backgroundColor: state.isFocused 
        ? '#0f172a' 
        : '#1e293b',
      boxShadow: state.isFocused 
        ? '0 0 0 3px rgba(96, 165, 250, 0.2)' 
        : 'none',
      transition: 'all 0.2s',
      '&:hover': {
        borderColor: '#60a5fa',
      },
    }),
    option: (base: any, state: any) => ({
      ...base,
      backgroundColor: state.isSelected 
        ? '#3b82f6' 
        : state.isFocused 
          ? '#1e293b' 
          : 'transparent',
      color: state.isSelected ? 'white' : '#e2e8f0',
      padding: '12px 16px',
      fontSize: '0.95rem',
      '&:active': {
        backgroundColor: '#3b82f6',
        color: 'white',
      },
    }),
    singleValue: (base: any) => ({
      ...base,
      color: '#e2e8f0',
    }),
    placeholder: (base: any) => ({
      ...base,
      color: '#64748b',
    }),
    dropdownIndicator: (base: any) => ({
      ...base,
      color: '#64748b',
      '&:hover': {
        color: '#60a5fa',
      },
    }),
    input: (base: any) => ({
      ...base,
      color: '#e2e8f0',
    }),
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative"
    >
      <div className="absolute left-4 top-1/2 transform -translate-y-1/2 z-10">
        <Globe className="h-5 w-5 text-gray-400 dark:text-gray-500" />
      </div>
      <Select
        options={countries}
        value={selectedCountry}
        onChange={(selectedOption) => setSelectedCountry(selectedOption!)}
        styles={document.documentElement.classList.contains('dark') ? darkModeStyles : customStyles}
        classNamePrefix="country-select"
        placeholder="Select your country"
        className="pl-12"
        components={{
          IndicatorSeparator: null,
        }}
      />
    </motion.div>
  );
};

export default CountrySelect;