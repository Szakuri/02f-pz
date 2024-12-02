drop DATABASE IF EXISTS nasz_projekt;
CREATE DATABASE nasz_projekt;

USE nasz_projekt;
-- Create Candidates Table
CREATE TABLE Candidate (
    PRIMARY KEY (id), 
	FOREIGN KEY(position_id) REFERENCES position (id),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    resume_text TEXT,
    skills VARCHAR(255),
    education VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'reviewed', 'recommended', 'not recommended') DEFAULT 'pending'
);

-- Create Job_Postings Table
CREATE TABLE Position  (
    PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    location VARCHAR(100),
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('open', 'closed') DEFAULT 'open'
);

CREATE TABLE keyword (
	id INTEGER NOT NULL, 
	word VARCHAR(50) NOT NULL, 
	position_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(position_id) REFERENCES position (id)
);

CREATE TABLE user (
	id INTEGER NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	UNIQUE (email)
);



