package com.workout.api.model;

public class ExerciseInfo {

    private String key;
    private String name;
    private boolean bilateral;

    public ExerciseInfo() {}

    public ExerciseInfo(String key, String name, boolean bilateral) {
        this.key = key;
        this.name = name;
        this.bilateral = bilateral;
    }

    public String getKey()              { return key; }
    public void setKey(String v)        { this.key = v; }

    public String getName()             { return name; }
    public void setName(String v)       { this.name = v; }

    public boolean isBilateral()        { return bilateral; }
    public void setBilateral(boolean v) { this.bilateral = v; }
}
