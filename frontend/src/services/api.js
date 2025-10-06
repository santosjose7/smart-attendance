import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Unauthorized - clear token and redirect to login
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth APIs
export const authAPI = {
  login: (credentials) => api.post('/auth/login', new URLSearchParams(credentials), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }),
  register: (data) => api.post('/auth/register', data),
  getCurrentUser: () => api.get('/auth/me'),
  verifyEmail: (token) => api.post('/auth/verify-email', { token }),
  forgotPassword: (email) => api.post('/auth/forgot-password', { email }),
  resetPassword: (token, newPassword) => api.post('/auth/reset-password', { token, new_password: newPassword }),
  changePassword: (currentPassword, newPassword) => api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
};

// Student APIs
export const studentAPI = {
  getProfile: () => api.get('/students/profile'),
  updateProfile: (data) => api.put('/students/profile', data),
  
  // Face Enrollment
  getFaceEnrollmentStatus: () => api.get('/students/face-enrollment/status'),
  uploadFacePhoto: (file, angle) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('angle', angle);
    return api.post('/students/face-enrollment/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  getEnrolledPhotos: () => api.get('/students/face-enrollment/photos'),
  deleteFacePhoto: (encodingId) => api.delete(`/students/face-enrollment/photos/${encodingId}`),
  resetFaceEnrollment: () => api.delete('/students/face-enrollment/reset'),
  
  // Courses & Attendance
  getMyCourses: () => api.get('/students/courses'),
  getCourseAttendance: (courseId) => api.get(`/students/courses/${courseId}/attendance`),
  getAttendanceSummary: () => api.get('/students/attendance/summary'),
  getTodayAttendance: () => api.get('/students/attendance/today'),
  getAttendanceHistory: (days = 30) => api.get(`/students/attendance/history?days=${days}`),
  getTodaySchedule: () => api.get('/students/schedule/today'),
};

// Attendance APIs
export const attendanceAPI = {
  // Student Check-in
  checkInWithFace: (sessionId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/attendance/check-in/face`, formData, {
      params: { session_id: sessionId },
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  checkInWithQR: (sessionId, qrToken, latitude, longitude) => 
    api.post('/attendance/check-in/qr', { session_id: sessionId, qr_token: qrToken, latitude, longitude }),
  
  // Kiosk Mode (No auth required)
  kioskCheckIn: (sessionId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return axios.post(`${API_BASE_URL}/attendance/sessions/${sessionId}/kiosk/check-in`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  kioskQRCheckIn: (sessionId, studentIdNumber) => 
    axios.post(`${API_BASE_URL}/attendance/sessions/${sessionId}/kiosk/qr-check-in`, { student_id_number: studentIdNumber }),
  getKioskStatus: (sessionId) => axios.get(`${API_BASE_URL}/attendance/sessions/${sessionId}/kiosk/status`),
  
  // Lecturer Session Management
  startSession: (sessionId) => api.post(`/attendance/sessions/${sessionId}/start`),
  endSession: (sessionId, markAbsent = true) => api.post(`/attendance/sessions/${sessionId}/end`, { mark_absent: markAbsent }),
  getQRCode: (sessionId) => api.get(`/attendance/sessions/${sessionId}/qr-code`),
  refreshQRCode: (sessionId) => api.post(`/attendance/sessions/${sessionId}/refresh-qr`),
  getLiveAttendance: (sessionId) => api.get(`/attendance/sessions/${sessionId}/live`),
  manualMarkAttendance: (sessionId, studentId, status, reason) => 
    api.post(`/attendance/sessions/${sessionId}/manual-mark`, { student_id: studentId, status, reason }),
};

// Lecturer APIs
export const lecturerAPI = {
  getProfile: () => api.get('/lecturers/profile'),
  updateProfile: (data) => api.put('/lecturers/profile', data),
  
  // Courses
  getMyCourses: () => api.get('/lecturers/courses'),
  getCourseStudents: (courseId) => api.get(`/lecturers/courses/${courseId}/students`),
  getCourseAttendanceSummary: (courseId) => api.get(`/lecturers/courses/${courseId}/attendance-summary`),
  
  // Sessions
  createSession: (data) => api.post('/lecturers/sessions/create', data),
  getMySessions: (dateFrom, dateTo, status) => api.get('/lecturers/sessions', { params: { date_from: dateFrom, date_to: dateTo, status } }),
  getTodaySessions: () => api.get('/lecturers/sessions/today'),
  getSessionDetails: (sessionId) => api.get(`/lecturers/sessions/${sessionId}`),
  updateSession: (sessionId, data) => api.put(`/lecturers/sessions/${sessionId}`, data),
  cancelSession: (sessionId, reason) => api.delete(`/lecturers/sessions/${sessionId}`, { data: { reason } }),
  
  // Reports
  getSessionAttendanceReport: (sessionId) => api.get(`/lecturers/sessions/${sessionId}/attendance-report`),
  
  // Communication
  emailStudents: (courseId, subject, message, recipients) => 
    api.post(`/lecturers/courses/${courseId}/email-students`, { subject, message, recipients }),
};

// Admin APIs
export const adminAPI = {
  getDashboard: () => api.get('/admin/dashboard'),
  getSystemHealth: () => api.get('/admin/system-health'),
  
  // User Management
  getAllUsers: (role, status, search, skip = 0, limit = 50) => 
    api.get('/admin/users', { params: { role, status, search, skip, limit } }),
  createUser: (data) => api.post('/admin/users/create', data),
  updateUser: (userId, data) => api.put(`/admin/users/${userId}`, data),
  resetUserPassword: (userId) => api.post(`/admin/users/${userId}/reset-password`),
  deleteUser: (userId) => api.delete(`/admin/users/${userId}`),
  bulkImportUsers: (file, role, sendEmails) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('role', role);
    formData.append('send_emails', sendEmails);
    return api.post('/admin/users/bulk-import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  
  // Course Management
  createCourse: (data) => api.post('/admin/courses/create', data),
  createCourseSection: (courseId, data) => api.post(`/admin/courses/${courseId}/sections`, data),
  assignLecturer: (courseId, lecturerId, sectionId, role) => 
    api.post(`/admin/courses/${courseId}/assign-lecturer`, { lecturer_id: lecturerId, section_id: sectionId, role }),
  enrollStudent: (courseId, studentId) => api.post(`/admin/courses/${courseId}/enroll-student`, { student_id: studentId }),
  
  // Reports
  getLowAttendanceReport: (threshold) => api.get('/admin/reports/low-attendance', { params: { threshold } }),
  getSystemUsageReport: (days = 30) => api.get('/admin/reports/system-usage', { params: { days } }),
};

export default api;