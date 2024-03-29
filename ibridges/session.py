"""session operations."""
import json
import warnings
from pathlib import Path
from typing import Optional, Union

import irods.session
from irods.session import NonAnonymousLoginWithoutPassword

LoginFail = {
    "NetworkException('Client-Server negotiation failure: CS_NEG_REFUSE,CS_NEG_REQUIRE')":
                          "Host, port, irods_client_server_policy or " + \
                          "irods_client_server_negotiation not set correctly in "+\
                          "irods_environment.json",
    "CAT_INVALID_USER(None,)": "User credentials are not accepted",
    "PAM_AUTH_PASSWORD_FAILED(None,)": "Wrong password",
    "CAT_PASSWORD_EXPIRED(None,)": "Cached password is expired",
    "CAT_INVALID_AUTHENTICATION(None,)": "Cached password is wrong"
    }

class Session:
    """Irods session authentication."""


    def __init__(self, irods_env: Optional[dict] = None,
                 irods_env_path: Optional[Union[str, Path]] = None,
                 password: Optional[str] = None, irods_home: Optional[str] = None):
        """IRODS authentication with Python client.

        Parameters
        ----------
        irods_env: dict
            Dictionary from irods_environment.json
        irods_env_path:
            File to read the dictionary from if irods_env is not supplied.
        password : str
            Plain text password.
        irods_home:
            Override the home directory of irods. Otherwise attempt to retrive the value
            from the irods environment dictionary. If it is not there either, then use
            /{zone}/home/{username}.

        """
        if irods_env is None and irods_env_path is None:
            raise ValueError("CONNECTION ERROR: no irods environment given.")
        if irods_env is not None and irods_env_path is not None:
            warnings.warn("Environment dictionary will be overwritten with irods environment file")
        if irods_env_path is not None:
            irods_env_path = Path(irods_env_path).expanduser()
            if irods_env_path.is_file():
                with irods_env_path.open("r", encoding="utf-8") as envfd:
                    irods_env = json.load(envfd)
                if not isinstance(irods_env, dict):
                    raise TypeError(f"Error reading environment file '{irods_env_path}': "
                                    f"expected dictionary, got {type(irods_env)}.")
            else:
                raise ValueError(f"CONNECTION ERROR: {irods_env_path} path does not exist.")
        self._password = password
        self._irods_env: dict = irods_env  # type: ignore
        self._irods_env_path = irods_env_path
        self._irods_session = self.connect()
        if irods_home is not None:
            self.home = irods_home
        if "irods_home" not in self._irods_env:
            self.home = '/'+self.zone+'/home/'+self.username

    def __enter__(self):
        """Connect to the iRods server if not already connected."""
        if not self.has_valid_irods_session():
            self.connect()
        return self

    def __exit__(self, exc_type, exc_value, exc_trace_back):
        """Disconnect from the iRods server."""
        self.close()

    @property
    def irods_session(self):
        """Get irods session."""
        return self._irods_session

    @property
    def home(self) -> str:
        """Current working directory for irods.

        In the iRods community this is known as 'irods_home', in file system terms
        it would be the current working directory.

        Returns
        -------
            The current working directory in the current session.

        """
        return self._irods_env["irods_home"]

    @home.setter
    def home(self, value):
        self._irods_env["irods_home"] = value

    # Authentication workflow methods
    def has_valid_irods_session(self) -> bool:
        """Check if the iRODS session is valid.

        Returns
        -------
        bool
            Is the session valid?

        """
        return self._irods_session is not None and self.server_version != ()

    def connect(self):
        """Establish an iRODS session."""
        user = self._irods_env.get('irods_user_name', '')
        if user == 'anonymous':
            # TODOx: implement and test for SSL enabled iRODS
            # self._irods_session = iRODSSession(user='anonymous',
            #                        password='',
            #                        zone=zone,
            #                        port=1247,
            #                        host=host)
            raise NotImplementedError
        # authentication with irods environment and password
        if self._password is None or self._password == '':
            # use cached password of .irodsA built into prc
            print("Auth without password")
            return self.authenticate_using_auth_file()

        # irods environment and given password
        print("Auth with password")
        return self.authenticate_using_password()

    def close(self) -> None:
        """Disconnect the irods session.

        This closes the connection, and makes the session available for
        reconnection with `connect`.
        """
        if self._irods_session is not None:
            self._irods_session.do_configure = {}
            self._irods_session.cleanup()
            self._irods_session = None

    def authenticate_using_password(self) -> None:
        """Authenticate with the iRods server using a password."""
        try:
            self._irods_session = irods.session.iRODSSession(password=self._password,
                                                             **self._irods_env)
            assert self._irods_session.server_version != ()
            return self._irods_session
        except ValueError as e:
            raise FileNotFoundError("Unexpected value in irods_environment.json; ") from e
        except Exception as e:
            if repr(e) in LoginFail:
                raise ValueError(LoginFail[repr(e)]+"; "+repr(e)) from e
            raise e

    def authenticate_using_auth_file(self):
        """Authenticate with an authentication file."""
        try:
            self._irods_session = irods.session.iRODSSession(
                    irods_env_file=self._irods_env_path)
            assert self._irods_session.server_version != ()
            return self._irods_session
        except ValueError as e:
            raise ValueError("Unexpected value in irods_environment.json; ") from e
        except NonAnonymousLoginWithoutPassword as e:
            raise ValueError("No cached password found.") from e
        except Exception as e:
            if repr(e) in LoginFail:
                raise ValueError(LoginFail[repr(e)]+", "+repr(e)) from e
            raise e

    def write_pam_password(self):
        """Store the password in the iRODS authentication file in obfuscated form."""
        connection = self._irods_session.pool.get_connection()
        pam_passwords = self._irods_session.pam_pw_negotiated
        if len(pam_passwords):
            irods_auth_file = self._irods_session.get_irods_password_file()
            with open(irods_auth_file, 'w', encoding='utf-8') as authfd:
                authfd.write(
                    irods.password_obfuscation.encode(pam_passwords[0]))
        else:
            warnings.warn('WARNING -- unable to cache obfuscated password locally')
        connection.release()

    @property
    def default_resc(self) -> str:
        """Default resource name from iRODS environment.

        Returns
        -------
        str
            Resource name.

        """
        if self._irods_session:
            try:
                return self._irods_session.default_resource
            except AttributeError:
                pass
        raise ValueError("'irods_default_resource' not set in iRODS configuration.")

    @property
    def host(self) -> str:
        """Retrieve hostname of the iRODS server.

        Returns
        -------
        str
            Hostname.

        """
        if self._irods_session:
            return self._irods_session.host
        return ''

    @property
    def port(self) -> str:
        """Retrieve port of the iRODS server.

        Returns
        -------
        str
            Port.

        """
        if self._irods_session:
            return self._irods_session.port
        return ''

    @property
    def server_version(self) -> tuple:
        """Retrieve version of the iRODS server.

        Returns
        -------
        tuple
            Server version: (major, minor, patch).

        """
        try:
            return self._irods_session.server_version
        except Exception as e:
            if repr(e) in LoginFail:
                raise ValueError(LoginFail[repr(e)]) from e
            raise e

    @property
    def username(self) -> str:
        """Retrieve username.

        Returns
        -------
        str
            Username.

        """
        if self._irods_session:
            return self._irods_session.username
        return ''

    @property
    def zone(self) -> str:
        """Retrieve the zone name.

        Returns
        -------
        str
            Zone.

        """
        if self._irods_session:
            return self._irods_session.zone
        return ''
