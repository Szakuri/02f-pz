drop DATABASE IF EXISTS nasz_projekt;
CREATE DATABASE nasz_projekt;

USE nasz_projekt;
-- Create Candidates Table
CREATE TABLE Candidates (
    candidate_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    linkedin_profile VARCHAR(200),
    resume_text TEXT,
    skills VARCHAR(255),
    education VARCHAR(255),
    experience TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'reviewed', 'recommended', 'not recommended') DEFAULT 'pending'
);

-- Create Job_Postings Table
CREATE TABLE Job_Postings (
    job_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    location VARCHAR(100),
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('open', 'closed') DEFAULT 'open'
);

-- Create Applications Table
CREATE TABLE Applications (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT,
    job_id INT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    evaluation_score FLOAT,
    status ENUM('submitted', 'under review', 'interview', 'rejected', 'hired') DEFAULT 'submitted',
    FOREIGN KEY (candidate_id) REFERENCES Candidates(candidate_id),
    FOREIGN KEY (job_id) REFERENCES Job_Postings(job_id)
);

-- Create Evaluation_Results Table
CREATE TABLE Evaluation_Results (
    evaluation_id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT,
    score FLOAT,
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES Applications(application_id)
);

-- Create Skills Table
CREATE TABLE Skills (
    skill_id INT AUTO_INCREMENT PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL UNIQUE
);

-- Create Candidate_Skills Table
CREATE TABLE Candidate_Skills (
    candidate_skill_id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT,
    skill_id INT,
    FOREIGN KEY (candidate_id) REFERENCES Candidates(candidate_id),
    FOREIGN KEY (skill_id) REFERENCES Skills(skill_id)
);

-- Create Feedback Table
CREATE TABLE Feedback (
    feedback_id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT,
    comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES Applications(application_id)
);
