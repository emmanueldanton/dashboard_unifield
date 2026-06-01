'use strict';

// Port exact de business/segments.py

const ENDING_SOON_DAYS = 7;

function isArchived(project) {
  return project.archived === true;
}

function isActive(project) {
  if (isArchived(project)) return false;
  if (!project.endDate) return true;
  return new Date(project.endDate) > Date.now();
}

function isEnding(project, endingDays = ENDING_SOON_DAYS) {
  if (!isActive(project)) return false;
  if (!project.endDate) return false;
  const msToEnd = new Date(project.endDate) - Date.now();
  const daysToEnd = msToEnd / 86400000;
  return daysToEnd > 0 && daysToEnd <= endingDays;
}

function projectStatus(project) {
  if (isArchived(project)) return 'archive';
  if (!isActive(project)) return 'termine';
  if (isEnding(project)) return 'se_terminant';
  return 'actif';
}

module.exports = { isActive, isEnding, isArchived, projectStatus };
