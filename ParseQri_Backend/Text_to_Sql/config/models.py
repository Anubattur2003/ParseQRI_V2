"""
Centralized Model Configuration for Text-to-SQL System

This module provides centralized model management for all agents in the system.
It maps agent types to specific Ollama models and provides configuration for
context windows to optimize latency.

Model Strategy:
- Use only two models to avoid Ollama thrashing
- dolphin3:8b: For orchestration tasks (intent, schema, response)
- deepseek-coder:6.7b: For SQL-specific tasks (generation, validation)
"""

import os
from typing import Dict, Optional
from enum import Enum


class AgentType(Enum):
    """Enumeration of agent types in the system."""
    SUPERVISOR = "supervisor"
    INTENT_CLASSIFICATION = "intent_classification"
    SCHEMA_FILTERING = "schema_filtering"
    SQL_GENERATION = "sql_generation"
    SQL_VALIDATION = "sql_validation"
    RESPONSE_FORMATTING = "response_formatting"


class ModelConfig:
    """Model configuration with context window settings."""
    
    # Model Registry - Maps agent types to Ollama models
    MODEL_REGISTRY: Dict[AgentType, str] = {
        AgentType.SUPERVISOR: "dolphin3:8b",
        AgentType.INTENT_CLASSIFICATION: "dolphin3:8b",
        AgentType.SCHEMA_FILTERING: "dolphin3:8b",
        AgentType.SQL_GENERATION: "deepseek-coder:6.7b",
        AgentType.SQL_VALIDATION: "deepseek-coder:6.7b",
        AgentType.RESPONSE_FORMATTING: "dolphin3:8b",
    }
    
    # Context Window Configuration (for latency optimization)
    CONTEXT_WINDOW: Dict[AgentType, int] = {
        AgentType.SUPERVISOR: 2048,
        AgentType.INTENT_CLASSIFICATION: 2048,
        AgentType.SCHEMA_FILTERING: 3072,
        AgentType.SQL_GENERATION: 4096,
        AgentType.SQL_VALIDATION: 3072,
        AgentType.RESPONSE_FORMATTING: 2048,
    }
    
    # Ollama API Configuration
    OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
    
    @classmethod
    def get_model_name(cls, agent_type: AgentType) -> str:
        """
        Get the model name for a specific agent type.
        
        Args:
            agent_type: The type of agent
            
        Returns:
            str: The Ollama model name
            
        Raises:
            ValueError: If agent type is not configured
        """
        if agent_type not in cls.MODEL_REGISTRY:
            raise ValueError(f"No model configured for agent type: {agent_type}")
        return cls.MODEL_REGISTRY[agent_type]
    
    @classmethod
    def get_context_window(cls, agent_type: AgentType) -> int:
        """
        Get the context window size for a specific agent type.
        
        Args:
            agent_type: The type of agent
            
        Returns:
            int: The context window size (OLLAMA_NUM_CTX)
            
        Raises:
            ValueError: If agent type is not configured
        """
        if agent_type not in cls.CONTEXT_WINDOW:
            raise ValueError(f"No context window configured for agent type: {agent_type}")
        return cls.CONTEXT_WINDOW[agent_type]
    
    @classmethod
    def get_model_config(cls, agent_type: AgentType) -> Dict[str, any]:
        """
        Get complete model configuration for an agent.
        
        Args:
            agent_type: The type of agent
            
        Returns:
            dict: Configuration including model name, context window, and API URL
        """
        return {
            "model_name": cls.get_model_name(agent_type),
            "context_window": cls.get_context_window(agent_type),
            "api_url": cls.OLLAMA_API_URL,
        }
    
    @classmethod
    def get_all_required_models(cls) -> set:
        """
        Get a set of all unique models required by the system.
        
        Returns:
            set: Set of unique model names
        """
        return set(cls.MODEL_REGISTRY.values())
    
    @classmethod
    def validate_models_available(cls) -> Dict[str, bool]:
        """
        Check which required models are available in Ollama.
        
        Returns:
            dict: Mapping of model names to availability status
            
        Note:
            This is a placeholder. Actual implementation would query Ollama API
            to check model availability using `/api/tags` endpoint.
        """
        import requests
        
        required_models = cls.get_all_required_models()
        availability = {}
        
        try:
            # Query Ollama for available models
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                available_models = {model["name"] for model in response.json().get("models", [])}
                for model in required_models:
                    availability[model] = model in available_models
            else:
                # If API call fails, assume models are available
                for model in required_models:
                    availability[model] = True
        except Exception as e:
            print(f"Warning: Could not check model availability: {str(e)}")
            # Assume models are available on error
            for model in required_models:
                availability[model] = True
        
        return availability


def get_model_for_agent(agent_type: AgentType) -> str:
    """
    Convenience function to get model name for an agent.
    
    Args:
        agent_type: The type of agent
        
    Returns:
        str: The Ollama model name
    """
    return ModelConfig.get_model_name(agent_type)


def get_config_for_agent(agent_type: AgentType) -> Dict[str, any]:
    """
    Convenience function to get complete configuration for an agent.
    
    Args:
        agent_type: The type of agent
        
    Returns:
        dict: Complete model configuration
    """
    return ModelConfig.get_model_config(agent_type)
