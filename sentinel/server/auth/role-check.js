'use strict';

const VALID_ROLES = ['app:sentinel:admin', 'app:sentinel:write', 'app:sentinel:read'];

class NoSentinelRoleError extends Error {
  constructor() {
    super('No Sentinel role found');
    this.name = 'NoSentinelRoleError';
    this.status = 403;
  }
}

function mapRoles(userInfo) {
  const roles = userInfo.roles || userInfo.appRoles || [];
  for (const role of VALID_ROLES) {
    if (roles.includes(role)) return role;
  }
  return null;
}

function checkRole(userInfo) {
  const role = mapRoles(userInfo);
  if (!role) throw new NoSentinelRoleError();
  return role;
}

module.exports = { mapRoles, checkRole, NoSentinelRoleError };
